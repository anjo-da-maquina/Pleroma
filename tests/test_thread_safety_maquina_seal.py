"""
tests/test_thread_safety_maquina_seal.py
==========================================
maquina_gatekeeper.py の`is_sanctuary_sealed()`/`set_sanctuary_sealed()`の
回帰テスト。GRIMOIRE.md §AD 参照。

背景: 封鎖ステータスが`threading.local()`(スレッドごとに独立)で管理されて
いたため、`enforce_maquina_seal`デコレータによって「封鎖済み」のメイン
スレッドの中で新規スレッドを一つ生成するだけで、その子スレッド内では
`is_sanctuary_sealed()`が常に`False`(threading.local()の既定値)を返し、
`ultimate_audit_hook`による「深層保護」(subprocess.Popen等の禁止操作の
遮断)が子スレッドでは一切働かなくなる重大なバイパス脆弱性があった。
`enforce_maquina_seal`は`_GLOBAL_SANCTUARY_LOCK`により呼び出し自体を
プロセス全体で直列化しているため、複数スレッドが同時に独立した封鎖状態
を持つ正当な理由はそもそも存在しない。封鎖フラグをプロセス全体で共有
するグローバル変数に修正し、本テストで固定する。

[2026-10] 実運用の `rsa` パッケージはこのサンドボックス環境のegress
ポリシー上インストールできないため、maquina_gatekeeper.pyの
`import rsa`を満たす疑似実装で代替する
(tests/test_provisioning_approval_flow.py と同一パターン)。
本テストはRSA署名検証ロジックそのものではなく、封鎖フラグの
スレッド間共有の挙動を検証するのが目的。

[注意1] `mini_pytest.py`は全テストファイルを同一プロセス内で読み込むため、
`sys.modules["rsa"]`はテストファイル間で共有される。本物の`rsa`パッケージ
が無い環境では、どのテストファイルが最初に読み込まれるかによって
インストールされる疑似実装が変わるため、他のテスト(例:
test_provisioning_approval_flow.py)が必要とする`newkeys`/`sign`等も
含めて、完全に互換な疑似実装を用意する(どちらが先に読み込まれても
後続のテストが`AttributeError`で壊れないようにするため)。

[注意2] 本ファイル名はあえて`test_openai_agent_loop_template.py`より
辞書順で後になるよう選んである。`mini_pytest.py`はテストファイルを
`sorted(tests_dir.glob("test_*.py"))`で辞書順に読み込むため、本ファイルが
先に読み込まれて`rsa`を(フェイクであれ)解決可能にしてしまうと、
`test_openai_agent_loop_template.py`が期待している「本物の`rsa`が無い
ことによる`ModuleNotFoundError`(既知の環境起因ERROR。GRIMOIRE.md §U参照)」
が、フェイクのRSA検証による本物の署名不一致エラー(`ValueError`)に変わって
しまい、無関係なFAILを発生させてしまうことを確認済み。ファイル名の
アルファベット順がこの副作用を避けるための前提条件になっている。
"""
import hashlib
import os
import sys
import threading
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

import maquina_gatekeeper as mg  # noqa: E402


def test_sealed_state_is_shared_across_threads():
    """
    [脆弱性修正の回帰テスト] メインスレッドで封鎖(sealed)した状態は、
    その中で新たに生成した子スレッドにも共有されなければならない。
    """
    mg._register_audit_hook_once()
    mg.set_sanctuary_sealed(True)
    try:
        result = {}

        def check_in_child_thread():
            result["sealed_in_child"] = mg.is_sanctuary_sealed()

        t = threading.Thread(target=check_in_child_thread)
        t.start()
        t.join()

        assert result["sealed_in_child"] is True, (
            "修正前の欠陥が再発している: 子スレッドで封鎖状態が共有されず、"
            "深層保護(ultimate_audit_hook)が無検査で素通りしてしまう。"
        )
    finally:
        mg.set_sanctuary_sealed(False)


def test_forbidden_operation_is_blocked_even_from_a_child_thread():
    """
    [脆弱性修正の回帰テスト] 封鎖中は、子スレッドから禁止操作
    (subprocess.Popen)を実行しようとしても、メインスレッドと同様に
    LossOfAtaraxiaで遮断されなければならない。
    """
    mg._register_audit_hook_once()
    mg.set_sanctuary_sealed(True)
    try:
        result = {}

        def evil_in_child_thread():
            try:
                import subprocess
                subprocess.Popen(["echo", "should_not_run"], stdout=subprocess.PIPE)
                result["blocked"] = False
            except mg.LossOfAtaraxia:
                result["blocked"] = True

        t = threading.Thread(target=evil_in_child_thread)
        t.start()
        t.join()

        assert result["blocked"] is True, (
            "修正前の欠陥が再発している: 子スレッドからのsubprocess.Popenが "
            "深層保護をすり抜けて実行されてしまった。"
        )
    finally:
        mg.set_sanctuary_sealed(False)


def test_unsealed_state_allows_normal_operation():
    """封鎖していない通常時は、禁止操作も(この監査フックによっては)遮断されない。"""
    mg._register_audit_hook_once()
    assert mg.is_sanctuary_sealed() is False
    import subprocess
    p = subprocess.Popen(["echo", "ok"], stdout=subprocess.PIPE)
    out, _ = p.communicate()
    assert out.decode().strip() == "ok"


def test_get_machine_id_is_not_a_constant_placeholder_on_linux():
    """[脆弱性修正の核心] GRIMOIRE.md §AS参照。以前の実装はWindows以外の
    プラットフォーム(本サンドボックスのLinuxを含む)では、ホストの識別
    情報を一切含まない固定文字列"UNKNOWN_MACHINE_ID"を無条件に返していた。
    本テストは実環境(Linux)で実際に/etc/machine-id由来の値が返ることを
    直接確認する(モックではなく、実機での動作そのものを固定する)。"""
    import platform
    from pathlib import Path

    if platform.system() != "Linux":
        return  # このテストはLinux環境でのみ意味を持つ(CI/サンドボックスはLinux)

    machine_id = mg.get_machine_id()
    assert machine_id != "UNKNOWN_MACHINE_ID", (
        "Linux上でget_machine_id()が固定のプレースホルダーを返している"
        "(修正前の欠陥が再発している)"
    )
    for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        if candidate.exists():
            assert machine_id == candidate.read_text(encoding="utf-8").strip()
            break
    else:
        raise AssertionError("どちらのmachine-idファイルも存在しない環境でのテストは想定外です")


def test_hardware_fingerprint_differs_between_different_machine_ids(monkeypatch):
    """[回帰防止] get_absolute_hardware_fingerprint()は、get_machine_id()の
    戻り値が異なれば異なる指紋を算出すること(個体識別として機能している
    ことの最低限の確認)。"""
    monkeypatch.setattr(mg, "get_machine_id", lambda: "machine-aaaa")
    fp1 = mg.get_absolute_hardware_fingerprint()
    monkeypatch.setattr(mg, "get_machine_id", lambda: "machine-bbbb")
    fp2 = mg.get_absolute_hardware_fingerprint()
    assert fp1 != fp2, "異なるマシンIDから同一の指紋が算出されている"


def test_get_machine_id_falls_back_to_documented_constant_on_unsupported_platform(monkeypatch):
    """[回帰防止] Windows/Linux/macOSのいずれでもない(未対応の)プラット
    フォームでは、既存の文書化された限界どおり固定文字列にフォールバック
    すること(この挙動自体は正常であり、検知対象ではない)。"""
    monkeypatch.setattr(mg.platform, "system", lambda: "SomeExoticOS")
    assert mg.get_machine_id() == "UNKNOWN_MACHINE_ID"
