"""
tests/test_audit_hook_registration_fails_closed.py
=====================================================
[脆弱性修正 2026-10 §BS] maquina_gatekeeper.py の`_register_audit_hook_once()`
の回帰テスト。

`_register_audit_hook_once()`は、本リポジトリの唯一の深層保護
(`ultimate_audit_hook`、`subprocess.Popen`・`os.system`・`ctypes`の
importなどをプロセス全体で遮断する`sys.addaudithook`ベースの監査フック)
を設置する唯一の箇所である。以前はこの設置処理全体が
`except Exception: pass`で囲まれていたため、`sys.addaudithook()`自体が
何らかの理由で例外を投げた場合、その失敗は完全に握り潰され、呼び出し元
(`enforce_maquina_seal`デコレータ・`_seal_sanctuary()`)は何も知らずに
処理を継続し、`set_sanctuary_sealed(True)`で「封鎖済み」を宣言して
しまっていた。つまり、唯一の安全装置の設置そのものが失敗しても、
「保護されている」という偽りの状態のまま後続処理が実行される
フェイルオープンだった(§BQ/§BRの「自壊理由のログ消失」とは別種だが、
同じく「異常時に静かに安全側へ倒れない」という構造的パターンの一つ)。

本テストは、`sys.addaudithook`自体が例外を投げる状況を模擬し、
修正後は(フェイルクローズの原則に従い)その例外がそのまま
`_register_audit_hook_once()`の呼び出し元まで伝播することを固定する。
"""
import maquina_gatekeeper as mg


def test_addaudithook_failure_propagates_instead_of_being_swallowed(monkeypatch):
    """[核心・§BS] sys.addaudithook()が例外を投げた場合、以前は
    `except Exception: pass`で握り潰され、_register_audit_hook_once()は
    何事もなく正常終了(呼び出し元は保護が有効だと誤信する)していた。
    修正後は、この例外がそのまま呼び出し元に伝播し(フェイルクローズ)、
    `_AUDIT_HOOK_REGISTERED`も真のまま更新されないことを確認する。"""
    monkeypatch.setattr(mg, "_AUDIT_HOOK_REGISTERED", False)

    def _boom(hook):
        raise RuntimeError("模擬: sys.addaudithookが何らかの理由で失敗した")

    monkeypatch.setattr(mg.sys, "addaudithook", _boom)

    try:
        mg._register_audit_hook_once()
        assert False, (
            "sys.addaudithook()が失敗したのに、_register_audit_hook_once()が"
            "例外を外へ伝播させず正常終了してしまった(フェイルオープンの再発)。"
        )
    except RuntimeError as e:
        assert "模擬" in str(e)

    assert mg._AUDIT_HOOK_REGISTERED is False, (
        "設置に失敗したにもかかわらず、_AUDIT_HOOK_REGISTEREDがTrueになっている。"
    )
