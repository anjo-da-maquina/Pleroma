"""
tests/test_raphael_remediation.py
=====================================
[新設 2026-11] angels/raphael_remediation.py の単体テスト。

本天使(「ラファエルの治癒」)は、`sefer/*.py`の全モジュールが構文的に
妥当(`ast.parse`でcompileできる)であることを検証する(自動修復監査:
壊れている場合はCIを早期に失敗させ、手動修復を促す)。天使群のテスト
カバレッジの棚卸しの過程で、専用テストが一件も存在しないことが判明
した。

`main()`は`ROOT / "sefer"`という固定パスを直接rglobするため、
`raphael_remediation.ROOT`を一時ディレクトリへmonkeypatchして検証
する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import raphael_remediation as rr


def test_real_repository_passes():
    """[実機の裏付け] 現時点のsefer/配下の全モジュールは構文的に正常
    であるため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rr.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_a_sefer_module_has_a_syntax_error(monkeypatch, tmp_path):
    """[核心] sefer/配下のいずれか1つのモジュールに構文エラーがある
    場合、正しくFAILし、該当ファイルパスを詳細に含めることを確認
    する。"""
    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    (sefer_dir / "good.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (sefer_dir / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(rr, "ROOT", tmp_path)
    try:
        rr.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_and_reports_all_broken_files_when_multiple_are_broken(monkeypatch, tmp_path):
    """複数のモジュールに構文エラーがある場合、両方を検知対象として
    報告することを確認する。"""
    import io
    from contextlib import redirect_stdout

    sefer_dir = tmp_path / "sefer"
    sub_dir = sefer_dir / "sub"
    sub_dir.mkdir(parents=True)
    (sefer_dir / "broken1.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    (sub_dir / "broken2.py").write_text("x = (\n", encoding="utf-8")
    monkeypatch.setattr(rr, "ROOT", tmp_path)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rr.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1
    out = buf.getvalue()
    assert "broken1.py" in out
    assert "broken2.py" in out


def test_passes_when_all_sefer_modules_including_nested_are_valid(monkeypatch, tmp_path):
    """サブディレクトリを含む全モジュールが構文的に正常であれば、想定
    どおりPASSする(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    sefer_dir = tmp_path / "sefer"
    sub_dir = sefer_dir / "sub"
    sub_dir.mkdir(parents=True)
    (sefer_dir / "a.py").write_text("x = 1\n", encoding="utf-8")
    (sub_dir / "b.py").write_text("y = 2\n", encoding="utf-8")
    monkeypatch.setattr(rr, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rr.main()
    assert "✅ PASS" in buf.getvalue()


def test_handles_bom_prefixed_files_correctly(monkeypatch, tmp_path):
    """BOM付き(utf-8-sig)のファイルも正しく読み込め、構文エラーが無い
    限りPASSすることを確認する(encoding='utf-8-sig'を使う実装の確認)。"""
    import io
    from contextlib import redirect_stdout

    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    (sefer_dir / "bom.py").write_bytes("x = 1\n".encode("utf-8-sig"))
    monkeypatch.setattr(rr, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rr.main()
    assert "✅ PASS" in buf.getvalue()
