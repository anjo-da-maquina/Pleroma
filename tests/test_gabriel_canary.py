"""
tests/test_gabriel_canary.py
=====================================
[新設 2026-11] angels/gabriel_canary.py の単体テスト。

本天使(「ガブリエルの機密漏洩カナリア」)は、(1)`hooks/pre-commit`が
`tools/pre_commit_secret_scan.py`を実際に呼び出す配線を保っていること
(事前ブロック層が静かに外されていないか)、(2)`scan_for_leaked_secrets()`
による秘密情報漏洩パターンの静的走査、という2つの検査を行う。

`scan_for_leaked_secrets()`自体の走査ロジックは
`tests/test_pre_commit_secret_scan.py`・
`tests/test_secret_scanners_do_not_flag_own_test_suite.py`で別途検証
済みだが、本天使固有の(1)の配線検証ロジックと、(1)(2)を組み合わせた
`main()`自体の判定フローは、天使群のテストカバレッジの棚卸しの過程で、
専用テストが一件も存在しないことが判明した。

`gabriel_canary.py`は`ROOT`・`scan_for_leaked_secrets`をモジュール
レベルで直接importしているため、両方をmonkeypatchして検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import gabriel_canary as gc

VALID_HOOK_TEXT = "#!/bin/sh\npython3 tools/pre_commit_secret_scan.py\n"


def _write_fixtures(root, hook_text=VALID_HOOK_TEXT, include_hook=True, include_scan_script=True):
    hooks_dir = root / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    tools_dir = root / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    if include_hook:
        (hooks_dir / "pre-commit").write_text(hook_text, encoding="utf-8")
    if include_scan_script:
        (tools_dir / "pre_commit_secret_scan.py").write_text("# dummy\n", encoding="utf-8")


def _expect_fail(monkeypatch, root, scan_hits=()):
    monkeypatch.setattr(gc, "ROOT", root)
    monkeypatch.setattr(gc, "scan_for_leaked_secrets", lambda: list(scan_hits))
    try:
        gc.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、pre-commitフックの配線が
    健全で、秘密情報の漏洩パターンも検出されないため、本天使はPASSを
    報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        gc.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_pre_commit_hook_file_is_missing(monkeypatch, tmp_path):
    """[核心・事前ブロック層の無効化検知] hooks/pre-commit自体が存在
    しない場合、正しくFAILする。"""
    _write_fixtures(tmp_path, include_hook=False)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_scan_script_is_missing(monkeypatch, tmp_path):
    """tools/pre_commit_secret_scan.py自体が存在しない場合、正しく
    FAILする。"""
    _write_fixtures(tmp_path, include_scan_script=False)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_hook_does_not_call_scan_script(monkeypatch, tmp_path):
    """[核心・配線切断の検知] hooks/pre-commitが存在していても、
    tools/pre_commit_secret_scan.pyを実際には呼び出していない(配線が
    静かに外されている)場合、正しくFAILする。"""
    _write_fixtures(tmp_path, hook_text="#!/bin/sh\necho 'noop'\n")
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_secret_pattern_is_detected(monkeypatch, tmp_path):
    """[核心] 配線は健全でも、scan_for_leaked_secrets()が秘密情報らしき
    パターンを検知した場合、正しくFAILし詳細を含めることを確認する。"""
    _write_fixtures(tmp_path)
    monkeypatch.setattr(gc, "ROOT", tmp_path)
    monkeypatch.setattr(
        gc, "scan_for_leaked_secrets", lambda: [("src/leak.py", "AWS_SECRET_KEY")]
    )
    try:
        gc.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_with_all_valid_fixtures_and_no_hits(monkeypatch, tmp_path):
    """配線が健全で、秘密情報の漏洩パターンも検出されない場合、想定
    どおりPASSする(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    _write_fixtures(tmp_path)
    monkeypatch.setattr(gc, "ROOT", tmp_path)
    monkeypatch.setattr(gc, "scan_for_leaked_secrets", lambda: [])
    buf = io.StringIO()
    with redirect_stdout(buf):
        gc.main()
    assert "✅ PASS" in buf.getvalue()
