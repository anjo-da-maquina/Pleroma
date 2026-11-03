"""
tests/test_principalities_e2e.py
=====================================
[新設 2026-11] angels/principalities_e2e.py の単体テスト。

本天使(「権天使の試練」)は、重要モジュール(sefer・anjo_interceptor)が
正しくimportでき、基本的な公開APIが期待通りに動作することをE2Eで検証
する。具体的には(1)`sefer.inquisition()`が既知の危険コード
(`os.system`)を検知すること、(2)`IntentInterceptor`がハニーポット
(`dummy_secrets/dummy_api_key.env`)へのアクセスを
`SpecificationGamingDetected`として検知すること、を確認する。
`anjo_interceptor`が未インストールの場合は情報ログのみでスキップする
設計になっている。

`sefer.inquisition()`・`IntentInterceptor`自体の実装は他のテストで
別途検証済みだが、本天使固有の「E2Eとして両者を実際に呼び出し、結果
(findings/例外)を正しく判定する」というラッパー判定ロジック自体は、
天使群のテストカバレッジの棚卸しの過程で、専用テストが一件も存在
しないことが判明した。

`main()`は`sefer`・`anjo_interceptor.intent_checker`をmain()内部で
ローカルimportするため、`sefer.inquisition`をモジュール属性として直接
monkeypatchし、`anjo_interceptor.intent_checker.IntentInterceptor`は
クラスメソッドをmonkeypatchする(サインダルフォンの望遠鏡と同様の局所
import対策)。モジュール未検出の分岐は`builtins.__import__`を一時的に
差し替えて再現する。
"""
import sys
import builtins
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import principalities_e2e as pe2e
import sefer
from anjo_interceptor.intent_checker import IntentInterceptor, SpecificationGamingDetected


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、sefer.inquisition()が
    既知の危険コードを検知し、IntentInterceptorがハニーポットへの
    アクセスを正しく検知するため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        pe2e.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_inquisition_detects_nothing(monkeypatch):
    """[核心] sefer.inquisition()が既知の危険コードに対して空の
    findings(偽の安全)を返す場合、正しくFAILする。"""
    monkeypatch.setattr(sefer, "inquisition", lambda code: [])
    try:
        pe2e.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_interceptor_does_not_detect_honeypot_access(monkeypatch):
    """[核心・フェイルオープン検知] IntentInterceptorがハニーポットへの
    アクセスに対して例外(SpecificationGamingDetected)を発生させず、
    静かに許可してしまう場合、正しくFAILする。"""
    monkeypatch.setattr(IntentInterceptor, "evaluate_action", lambda self, action_json: None)
    try:
        pe2e.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_reports_info_and_passes_when_anjo_interceptor_is_absent(monkeypatch):
    """anjo_interceptorモジュール自体が未インストールの場合、E2E検査を
    スキップする情報ログを出しつつ、残りの検査(inquisition)が正常で
    あれば正しくPASSすることを確認する(本天使の意図的な設計:
    任意のモジュールとして扱う)。"""
    import io
    from contextlib import redirect_stdout

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "anjo_interceptor.intent_checker" or name.startswith("anjo_interceptor."):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    buf = io.StringIO()
    with redirect_stdout(buf):
        pe2e.main()
    out = buf.getvalue()
    assert "✅ PASS" in out
    assert "スキップ" in out
