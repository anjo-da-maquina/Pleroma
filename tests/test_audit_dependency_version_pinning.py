"""
tests/test_audit_dependency_version_pinning.py
=====================================
[新設 2026-11] angels/audit_dependency_version_pinning.py の単体テスト。

本天使(「オファニムの眼」)は、`requirements.txt`の全依存パッケージが
バージョン固定(`==`)されているかを検証する(サプライチェーン攻撃対策
の基本)。天使群のテストカバレッジの棚卸しの過程で、専用テストが
一件も存在しないことが判明した(`tests/test_guard_html_external_script_injection.py`
は別の天使`angels/guard_html_external_script_injection.py`向けのテストであり、本天使
`angels/audit_dependency_version_pinning.py`は対象外だった)。

`main()`は`ROOT / "requirements.txt"`という固定パスを直接読むため、
`audit_dependency_version_pinning.ROOT`を一時ディレクトリへmonkeypatchして検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import audit_dependency_version_pinning as oe


def _expect_fail(monkeypatch, root):
    monkeypatch.setattr(oe, "ROOT", root)
    try:
        oe.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_real_repository_passes():
    """[実機の裏付け] 現時点のrequirements.txtは、全依存がバージョン
    固定されているため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        oe.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_requirements_txt_is_missing(monkeypatch, tmp_path):
    """requirements.txt自体が存在しない場合、正しくFAILする。"""
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_a_dependency_is_unpinned(monkeypatch, tmp_path):
    """[核心・サプライチェーン攻撃対策] バージョン未固定の依存
    (==を含まない行)が1件でもあれば、正しくFAILし詳細を含めることを
    確認する。"""
    (tmp_path / "requirements.txt").write_text(
        "requests==2.31.0\nnumpy\npytest==8.0.0\n", encoding="utf-8"
    )
    monkeypatch.setattr(oe, "ROOT", tmp_path)
    try:
        oe.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_all_dependencies_are_pinned_with_comments_and_blanks(monkeypatch, tmp_path):
    """全依存がバージョン固定されている場合、コメント行・空行が混在
    していても正しくPASSする(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    (tmp_path / "requirements.txt").write_text(
        "# コメント行\nrequests==2.31.0\n\npytest==8.0.0\n", encoding="utf-8"
    )
    monkeypatch.setattr(oe, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        oe.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_with_empty_requirements_file(monkeypatch, tmp_path):
    """requirements.txtが存在していても内容が空の場合、未固定の依存も
    無いため正しくPASSする(空集合の空虚なPASSではなく、検査対象が
    実際に0件であることの明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(oe, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        oe.main()
    assert "✅ PASS" in buf.getvalue()
