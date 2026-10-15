"""
tests/test_junit_xml_exporter_chain_verification.py
=======================================================
[脆弱性修正 2026-10 §BN] adapters/junit_xml_exporter.py の回帰テスト。

以前の export_zkp_to_junit() は、zk_audit_trail.json のHMAC連鎖を一切
検証せず、testsuiteのfailures/errors属性を常に"0"で固定していた。
CI/CDダッシュボードはこのJUnit XMLの内容だけを見るため、根底の監査
ログが実際に改ざんされていても、ダッシュボード上は常に緑色になる
(見せかけの保護)という欠陥だった。

本テストは、(1) 改ざんされていない正当な連鎖はfailures="0"のまま
であること、(2) 改ざんされた連鎖は実際にfailures="1"かつ<failure>要素
で検知されること、(3) angels/heavenly_tablets_zkp.py側もこれを読んで
CI自体を失敗させること、を固定する。

実運用の`rsa`パッケージ(PyPI配布)は、本テストを実行するサンドボックス
環境にはインストールできない(§BK時点のtests/test_provisioning_approval_flow.py
と同じ事情)。maquina_gatekeeper.pyはモジュール読み込み時に`import rsa`
するため、本テストでも同じ最小限の疑似実装で代替する。
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "adapters")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "angels")))

if "rsa" not in sys.modules:
    # [§BN] このスタブは本ファイル単独では rsa.sign/rsa.verify を使わないが、
    # 他のテストファイル(tests/test_provisioning_approval_flow.py等)と
    # 同じ"if 'rsa' not in sys.modules"というガードを使っているため、
    # mini_pytest.pyが全テストファイルを同一プロセス内で実行する都合上、
    # どちらが先に実行されても困らないよう、完全な互換スタブ(sign/verify
    # を含む)として用意する。不完全なスタブを先に登録してしまうと、後から
    # 実行される他のテストファイルが「もう登録されているから自分は何もしない」
    # と判断し、rsa.sign呼び出しでAttributeErrorになる実害があった
    # (実機のmini_pytest.py実行で確認済み)。
    _fake_rsa = types.ModuleType("rsa")
    import hashlib as _hashlib

    class _FakeKey:
        def __init__(self, seed: bytes):
            self._seed = seed

        def save_pkcs1(self):
            return b"-----BEGIN RSA PUBLIC KEY-----\n" + self._seed.hex().encode("ascii") + b"\n-----END RSA PUBLIC KEY-----"

    class _FakePublicKeyModule:
        @staticmethod
        def load_pkcs1(pem_bytes):
            return _FakeKey(pem_bytes)

    def _fake_newkeys(bits):
        import os as _os
        seed = _os.urandom(16)
        return _FakeKey(seed), _FakeKey(seed)

    def _fake_sign(message, priv_key, hash_method):
        return _hashlib.sha256(message + priv_key._seed).digest()

    def _fake_verify(message, signature, pub_key):
        if signature != _hashlib.sha256(message + pub_key._seed).digest():
            raise ValueError("signature mismatch")
        return True

    _fake_rsa.newkeys = _fake_newkeys
    _fake_rsa.sign = _fake_sign
    _fake_rsa.verify = _fake_verify
    _fake_rsa.PublicKey = _FakePublicKeyModule
    sys.modules["rsa"] = _fake_rsa


def _build_valid_chain(tmp_path, monkeypatch, n=3):
    """maquina_gatekeeper.ZKAuditTrail を使って、本物のHMAC連鎖を
    tmp_path内に実際に構築する(signing_key・trailファイルとも)。"""
    import maquina_gatekeeper as mg

    trail_file = tmp_path / "zk_audit_trail.json"
    key_file = tmp_path / ".zk_audit_signing_key"
    monkeypatch.setattr(mg.ZKAuditTrail, "FILE_NAME", str(trail_file))
    monkeypatch.setattr(mg, "_ZK_SIGNING_KEY_PATH", key_file)
    monkeypatch.setattr(mg.ZKAuditTrail, "REMOTE_LEDGER_MOCK", str(tmp_path / "remote_ledger_sync.log"))
    monkeypatch.setattr(mg, "_LAST_TIMESTAMP", mg.datetime(1970, 1, 1))

    for i in range(n):
        mg.ZKAuditTrail.verify_and_record(f"action_{i}")
    return trail_file, key_file


def test_untampered_chain_reports_zero_failures(tmp_path, monkeypatch):
    """[回帰防止] 改ざんの無い正当な連鎖は、修正後も引き続きfailures="0"
    で出力されること(過剰検知の回帰防止)。"""
    trail_file, key_file = _build_valid_chain(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)

    import junit_xml_exporter as jxe
    import importlib
    importlib.reload(jxe)
    out_path = tmp_path / "zk_audit_report.xml"
    jxe.export_zkp_to_junit(json_path=str(trail_file), xml_path=str(out_path))

    import xml.etree.ElementTree as ET
    tree = ET.parse(out_path)
    testsuite = tree.getroot().find("testsuite")
    assert testsuite.get("failures") == "0"


def test_tampered_chain_is_detected_and_reported_as_failure(tmp_path, monkeypatch):
    """[核心・§BN] 連鎖が実際に改ざんされている場合、JUnit XML上で
    failures="1"かつ<failure>要素として検知されること。以前の実装は
    どれだけ改ざんされていても常にfailures="0"を出力していた。"""
    trail_file, key_file = _build_valid_chain(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)

    # ファイル上の連鎖を直接改ざんする(actionフィールドを書き換え、
    # current_hashとの整合性を破壊する)。
    trail = json.loads(trail_file.read_text(encoding="utf-8"))
    trail[1]["action"] = "TAMPERED_ACTION"
    trail_file.write_text(json.dumps(trail), encoding="utf-8")

    import junit_xml_exporter as jxe
    import importlib
    importlib.reload(jxe)
    out_path = tmp_path / "zk_audit_report.xml"
    jxe.export_zkp_to_junit(json_path=str(trail_file), xml_path=str(out_path))

    import xml.etree.ElementTree as ET
    tree = ET.parse(out_path)
    testsuite = tree.getroot().find("testsuite")
    assert testsuite.get("failures") == "1", (
        "連鎖が改ざんされているのにJUnit XMLがfailures=\"0\"を報告している"
        "(CIダッシュボードが常に緑色になる見せかけの保護)"
    )
    failure_testcases = [
        tc for tc in testsuite.findall("testcase") if tc.find("failure") is not None
    ]
    assert len(failure_testcases) == 1


def test_heavenly_tablets_zkp_fails_ci_when_chain_is_tampered(tmp_path, monkeypatch):
    """[統合] angels/heavenly_tablets_zkp.py自身も、エクスポートされた
    JUnit XMLのfailures属性を見てCI自体を失敗させること(ダッシュボード
    だけに判定を委ねない)。"""
    trail_file, key_file = _build_valid_chain(tmp_path, monkeypatch, n=2)
    trail = json.loads(trail_file.read_text(encoding="utf-8"))
    trail[0]["action"] = "TAMPERED_ACTION"
    trail_file.write_text(json.dumps(trail), encoding="utf-8")

    import heavenly_tablets_zkp as htz
    import importlib
    importlib.reload(htz)
    monkeypatch.setattr(htz, "ROOT", tmp_path)

    import pytest
    with pytest.raises(SystemExit) as exc_info:
        htz.main()
    assert exc_info.value.code == 1
