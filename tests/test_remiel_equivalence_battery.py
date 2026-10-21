"""
tests/test_remiel_equivalence_battery.py
===========================================
[新設 2026-10 §BW] angels/remiel_equivalence_battery.py の単体テスト。

§11.9フェーズF(ブロックリスト回避・等価構文迂回の一般化)。実際に
`anjo_interceptor/intent_checker.py`で発見・修正した`import os.path`
によるブロックリスト回避(§BW)を、リポジトリに存在する3つの
ブロックリスト型AST静的解析器(Gabriel・IntentInterceptor・
CognitiveScanner)に対して継続的に再現・検証する天使の、自己レッド
チームの結果を固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import remiel_equivalence_battery as reb


def test_real_repository_battery_passes():
    """[実機の裏付け] 現時点の3つの検査器すべてが、既知の等価構文回避
    ペイロードを全て正しく遮断することを確認する(§BWの修正の回帰防止)。"""
    failures = reb.run_battery()
    assert failures == [], f"遮断に失敗した組み合わせがあります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        reb.main()
    assert "✅ PASS" in buf.getvalue()


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §BWの修正前の`IntentInterceptor`相当
    の、`alias.name in forbidden_modules`という完全一致のみで判定する
    (ドット区切りを考慮しない)素朴な実装に戻した場合、本天使が正しく
    「遮断されなかった」として検知することを、実際に確認する。"""
    import ast
    from anjo_interceptor.intent_checker import SpecificationGamingDetected

    def _vulnerable_check_intent_checker(code: str) -> bool:
        """§BW修正前の実装(ドット区切りを考慮しない完全一致判定)を
        ここだけ再現する、意図的に脆弱なスタブ。"""
        tree = ast.parse(code)
        forbidden_modules = {"os", "subprocess", "sys", "pty"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_modules:  # [修正前] ドット分割なし
                        return True
        return False

    patched_checkers = [
        (name, _vulnerable_check_intent_checker if name.startswith("anjo_interceptor") else fn)
        for name, fn in reb.CHECKERS
    ]
    monkeypatch.setattr(reb, "CHECKERS", patched_checkers)

    failures = reb.run_battery()
    failing_payloads = {p for c, p, r in failures if c.startswith("anjo_interceptor")}
    assert "dotted_submodule_import" in failing_payloads
    assert "dotted_from_import" in failing_payloads


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom(code: str) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(reb, "CHECKERS", [("boom-checker", _boom)])
    failures = reb.run_battery()
    assert len(failures) == len(reb.MUST_BLOCK_PAYLOADS)
    assert all("boom" in r for _, _, r in failures)
