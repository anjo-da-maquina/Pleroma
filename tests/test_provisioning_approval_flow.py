"""
tests/test_provisioning_approval_flow.py
==========================================
adapters/provisioning_agent.py の再構築(2026-10)を検証する回帰テスト。
詳細な経緯は同モジュールのdocstring、および GRIMOIRE.md §O 参照。

確認する点:
  1. provision_sanctuary() が、maquina_gatekeeper.py の
     MAQUINA_PUBLIC_KEY_PEM を直接書き換えず、また ataraxia_certificate.json
     を即座に発行しないこと(自己署名による無条件自己承認の防止)。
  2. 提案が sefer/provisioning_pending.json に
     status="PENDING_HUMAN_REVIEW" として積まれること。
  3. tools/promote_provisioning_seal.py --approve で初めて
     MAQUINA_PUBLIC_KEY_PEM の更新と証明書発行が行われること。
  4. --reject の場合は何も変更されないこと。
"""
import hashlib
import json
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "adapters")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))

# [2026-10] 実運用の `rsa` パッケージ(PyPI配布)は、本テストを実行する
# サンドボックス環境にはインストールできない(組織のegressポリシーでPyPIが
# 遮断されているため)。maquina_gatekeeper.py / provisioning_agent.py は
# モジュール読み込み時に `import rsa` するため、本テストはキュー登録→
# 承認/拒否という「どのファイルが・いつ・何を書き換えるか」という構造を
# 検証するのが目的であり、署名の暗号学的な正しさそのものはテスト範囲外
# なので、最小限の疑似実装で代替する(本番コードには一切含めない)。
if "rsa" not in sys.modules:
    _fake_rsa = types.ModuleType("rsa")

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
        seed = os.urandom(16)
        return _FakeKey(seed), _FakeKey(seed)

    def _fake_sign(message, priv_key, hash_method):
        return hashlib.sha256(message + priv_key._seed).digest()

    def _fake_verify(message, signature, pub_key):
        if signature != hashlib.sha256(message + pub_key._seed).digest():
            raise ValueError("signature mismatch")
        return True

    _fake_rsa.newkeys = _fake_newkeys
    _fake_rsa.sign = _fake_sign
    _fake_rsa.verify = _fake_verify
    _fake_rsa.PublicKey = _FakePublicKeyModule
    sys.modules["rsa"] = _fake_rsa


def test_provision_sanctuary_does_not_mutate_gatekeeper_or_issue_cert(tmp_path, monkeypatch):
    import provisioning_agent as pa
    import maquina_gatekeeper as mg

    pending_file = tmp_path / "provisioning_pending.json"
    cert_file = tmp_path / "ataraxia_certificate.json"
    gatekeeper_file = tmp_path / "maquina_gatekeeper.py"
    gatekeeper_file.write_text(mg.__file__ and open(mg.__file__, encoding="utf-8").read(), encoding="utf-8")
    original_gatekeeper_src = gatekeeper_file.read_text(encoding="utf-8")

    monkeypatch.setattr(pa, "PENDING_PATH", str(pending_file))

    pa.provision_sanctuary(client_id="test-client")

    assert not cert_file.exists(), "ataraxia_certificate.json が即座に発行されてしまっている(人間承認を経ない自己署名)"
    assert gatekeeper_file.read_text(encoding="utf-8") == original_gatekeeper_src, (
        "maquina_gatekeeper.py のMAQUINA_PUBLIC_KEY_PEMが提案者自身によって書き換えられてしまっている"
    )

    pending = json.loads(pending_file.read_text(encoding="utf-8"))
    assert len(pending) == 1
    assert pending[0]["status"] == "PENDING_HUMAN_REVIEW"
    assert pending[0]["payload"]["client_id"] == "test-client"
    assert "public_key_pem" in pending[0]
    assert "signature" in pending[0]


def test_promote_provisioning_seal_approval_flow(tmp_path, monkeypatch):
    import provisioning_agent as pa
    import promote_provisioning_seal as pps
    import maquina_gatekeeper as mg

    pending_file = tmp_path / "provisioning_pending.json"
    cert_file = tmp_path / "ataraxia_certificate.json"
    gatekeeper_file = tmp_path / "maquina_gatekeeper.py"
    gatekeeper_file.write_text(open(mg.__file__, encoding="utf-8").read(), encoding="utf-8")

    monkeypatch.setattr(pa, "PENDING_PATH", str(pending_file))
    monkeypatch.setattr(pps, "PENDING_PATH", pending_file)
    monkeypatch.setattr(pps, "CERT_PATH", cert_file)
    monkeypatch.setattr(pps, "GATEKEEPER_PATH", gatekeeper_file)

    pa.provision_sanctuary(client_id="test-client-2")
    pps.approve("test-client-2")

    assert cert_file.exists(), "承認後もataraxia_certificate.jsonが発行されていない"
    cert = json.loads(cert_file.read_text(encoding="utf-8"))
    assert cert["payload"]["client_id"] == "test-client-2"

    new_gatekeeper_src = gatekeeper_file.read_text(encoding="utf-8")
    pending = json.loads(pending_file.read_text(encoding="utf-8"))
    proposed_pubkey = pending[0]["public_key_pem"]
    assert proposed_pubkey in new_gatekeeper_src, (
        "承認したのにMAQUINA_PUBLIC_KEY_PEMが更新されていない"
    )
    assert pending[0]["status"] == "APPROVED"


def test_promote_provisioning_seal_supersedes_stale_duplicate_pending_entries(tmp_path, monkeypatch):
    """[脆弱性修正 2026-10 §BK] 同一client_idに複数の承認待ち提案がある場合、
    最新のものを承認すると、古い重複提案は二度と承認待ちとして拾われない
    よう"SUPERSEDED"になる(=後から誤って再承認され、信頼の起点が古い
    内容へロールバックされることを防ぐ)。"""
    import promote_provisioning_seal as pps

    pending_file = tmp_path / "provisioning_pending.json"
    cert_file = tmp_path / "ataraxia_certificate.json"
    gatekeeper_file = tmp_path / "maquina_gatekeeper.py"
    import maquina_gatekeeper as mg
    gatekeeper_file.write_text(open(mg.__file__, encoding="utf-8").read(), encoding="utf-8")

    monkeypatch.setattr(pps, "PENDING_PATH", pending_file)
    monkeypatch.setattr(pps, "CERT_PATH", cert_file)
    monkeypatch.setattr(pps, "GATEKEEPER_PATH", gatekeeper_file)

    old_pem = "-----BEGIN RSA PUBLIC KEY-----\nOLDKEYDATA\n-----END RSA PUBLIC KEY-----"
    new_pem = "-----BEGIN RSA PUBLIC KEY-----\nNEWKEYDATA\n-----END RSA PUBLIC KEY-----"
    pending = [
        {
            "payload": {"client_id": "dup-client", "hardware_fingerprint": "OLD_FP", "valid_until": "2026-01-01T00:00:00Z"},
            "public_key_pem": old_pem, "signature": "old_sig",
            "requested_at": "2026-09-01T00:00:00Z", "status": "PENDING_HUMAN_REVIEW",
        },
        {
            "payload": {"client_id": "dup-client", "hardware_fingerprint": "NEW_FP", "valid_until": "2027-01-01T00:00:00Z"},
            "public_key_pem": new_pem, "signature": "new_sig",
            "requested_at": "2026-10-01T00:00:00Z", "status": "PENDING_HUMAN_REVIEW",
        },
    ]
    pending_file.write_text(json.dumps(pending), encoding="utf-8")

    pps.approve("dup-client")

    saved = json.loads(pending_file.read_text(encoding="utf-8"))
    statuses = {p["payload"]["hardware_fingerprint"]: p["status"] for p in saved}
    assert statuses["NEW_FP"] == "APPROVED"
    assert statuses["OLD_FP"] == "SUPERSEDED", (
        "古い重複提案がPENDING_HUMAN_REVIEWのまま残っており、将来誤って"
        "再承認され信頼の起点がロールバックされる危険が残っている"
    )

    cert_fp_after_first = json.loads(cert_file.read_text(encoding="utf-8"))["payload"]["hardware_fingerprint"]
    assert cert_fp_after_first == "NEW_FP"

    # 後から(例えば残った提案を片付けるつもりで)同じclient_idを再度approveしても、
    # SUPERSEDEDになったOLD_FPはもう拾われず、信頼の起点は変化しない。
    pps.approve("dup-client")
    cert_fp_after_second = json.loads(cert_file.read_text(encoding="utf-8"))["payload"]["hardware_fingerprint"]
    assert cert_fp_after_second == "NEW_FP", (
        "古い重複提案が再承認され、信頼の起点が古い内容へロールバックされてしまった"
    )


def test_promote_provisioning_seal_reject_does_not_touch_gatekeeper(tmp_path, monkeypatch):
    import provisioning_agent as pa
    import promote_provisioning_seal as pps
    import maquina_gatekeeper as mg

    pending_file = tmp_path / "provisioning_pending.json"
    cert_file = tmp_path / "ataraxia_certificate.json"
    gatekeeper_file = tmp_path / "maquina_gatekeeper.py"
    original_src = open(mg.__file__, encoding="utf-8").read()
    gatekeeper_file.write_text(original_src, encoding="utf-8")

    monkeypatch.setattr(pa, "PENDING_PATH", str(pending_file))
    monkeypatch.setattr(pps, "PENDING_PATH", pending_file)
    monkeypatch.setattr(pps, "CERT_PATH", cert_file)
    monkeypatch.setattr(pps, "GATEKEEPER_PATH", gatekeeper_file)

    pa.provision_sanctuary(client_id="test-client-3")
    pps.reject("test-client-3")

    assert not cert_file.exists()
    assert gatekeeper_file.read_text(encoding="utf-8") == original_src
    pending = json.loads(pending_file.read_text(encoding="utf-8"))
    assert pending[0]["status"] == "REJECTED"
