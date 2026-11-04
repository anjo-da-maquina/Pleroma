"""
tests/test_audit_blocklist_regression.py
=====================================
[新設 2026-11] angels/audit_blocklist_regression.py の単体テスト。

本天使(「ジョフィエルの灯」)は、`sefer.inquisition()`の禁止モジュール/
関数リストが、既知のベースライン(`BASELINE_FORBIDDEN_MODULES`・
`BASELINE_FORBIDDEN_FUNCS`)より静かに弱体化(縮小)していないかを、
`sefer.inquisition`の実際のソースコードをテキストとして静的走査する
ことで検証する(意味論的ドリフト検知)。天使群のテストカバレッジの
棚卸しの過程で、専用テストが一件も存在しないことが判明した。

`main()`は`inspect.getsource(sefer.inquisition)`を直接呼ぶため、標準
ライブラリの`inspect.getsource`自体を一時的にmonkeypatchし、実際の
`sefer.inquisition`の実装を介さずに、本天使固有の「ベースラインとの
差分判定」ロジックのみを単独で検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import audit_blocklist_regression as js
import inspect as inspect_module


def _fake_source_containing(tokens, quote="'"):
    """与えられたトークン群(モジュール名・関数名)を文字列リテラルとして
    含む、架空のinquisition()ソースコード文字列を組み立てる。"""
    lines = ["def inquisition(code):"]
    for tok in tokens:
        lines.append(f"    if {quote}{tok}{quote} in code: raise PermissionError()")
    lines.append("    return code")
    return "\n".join(lines) + "\n"


FULL_BASELINE_TOKENS = list(js.BASELINE_FORBIDDEN_MODULES) + list(js.BASELINE_FORBIDDEN_FUNCS)


def test_real_repository_passes():
    """[実機の裏付け] 現時点のsefer.inquisition()には、ベースラインの
    禁止モジュール/関数が全て含まれているため、本天使はPASSを報告
    する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        js.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_a_baseline_module_is_missing(monkeypatch):
    """[核心・意味論的ドリフト検知] ベースラインの禁止モジュールの
    うち1件(例: pickle)がソースから欠落している場合、正しくFAIL
    する。"""
    tokens = [t for t in FULL_BASELINE_TOKENS if t != "pickle"]
    monkeypatch.setattr(inspect_module, "getsource", lambda fn: _fake_source_containing(tokens))
    try:
        js.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_a_baseline_func_is_missing(monkeypatch):
    """[核心・意味論的ドリフト検知] ベースラインの禁止関数のうち1件
    (例: eval)がソースから欠落している場合、正しくFAILする。"""
    tokens = [t for t in FULL_BASELINE_TOKENS if t != "eval"]
    monkeypatch.setattr(inspect_module, "getsource", lambda fn: _fake_source_containing(tokens))
    try:
        js.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_all_baseline_tokens_are_present(monkeypatch):
    """ベースラインの全モジュール・全関数がソース中に(いずれかの引用
    形式で)含まれていれば、想定どおりPASSする(回帰防止のための明示的
    な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(
        inspect_module, "getsource", lambda fn: _fake_source_containing(FULL_BASELINE_TOKENS)
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        js.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_when_tokens_use_double_quotes(monkeypatch):
    """シングルクオート("'pickle'")ではなくダブルクオート('"pickle"')
    で記述されていても、正しく検知してPASSすることを確認する(どちらの
    引用形式でも検知する実装の確認)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(
        inspect_module,
        "getsource",
        lambda fn: _fake_source_containing(FULL_BASELINE_TOKENS, quote='"'),
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        js.main()
    assert "✅ PASS" in buf.getvalue()
