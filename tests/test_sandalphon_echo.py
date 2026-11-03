"""
tests/test_sandalphon_echo.py
=====================================
[新設 2026-11] angels/sandalphon_echo.py の単体テスト。

本天使(「サンダルフォンの響き」)は、監査証跡ファイル
(`sefer/audit_chain.jsonl`)自体の存在・可読性・各行がJSONLとして
妥当な形式であることを検証する。天使群のテストカバレッジの棚卸しの
過程で、専用テストが一件も存在しないことが判明した。

`main()`は`ROOT / "sefer" / "audit_chain.jsonl"`という固定パスを直接
参照するため、`sandalphon_echo.ROOT`をテストごとに一時ディレクトリへ
monkeypatchして検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import sandalphon_echo as se


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリの実際の監査証跡は全行が正しい
    JSONLであるため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        se.main()
    assert "✅ PASS" in buf.getvalue()


def test_reports_not_applicable_when_chain_file_is_missing(monkeypatch, tmp_path):
    """監査チェーンファイル自体が存在しない場合(違反が一度も記録されて
    いない、またはチェーン自体が未初期化)は、PASSではなくNOT_APPLICABLE
    を報告する(§BOで修正したPASS/NOT_APPLICABLE混同の再発防止と同じ
    方針)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(se, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        se.main()
    assert "⬜ NOT_APPLICABLE" in buf.getvalue()


def test_fails_when_jsonl_has_malformed_lines(monkeypatch, tmp_path):
    """[核心] 監査証跡に1行でもJSONLとしてパース不能な行があれば、本
    天使が正しくFAIL(sys.exit(1))することを確認する。"""
    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    log_path = sefer_dir / "audit_chain.jsonl"
    log_path.write_text(
        '{"event": "ok", "n": 1}\n'
        "this is not valid json\n"
        '{"event": "ok", "n": 2}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(se, "ROOT", tmp_path)
    try:
        se.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_all_lines_are_valid_jsonl(monkeypatch, tmp_path):
    """全行が正しいJSONLであれば、想定どおりPASSする(回帰防止のための
    明示的な固定)。空行はスキップされ、カウント対象にならないことも
    合わせて確認する。"""
    import io
    from contextlib import redirect_stdout

    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    log_path = sefer_dir / "audit_chain.jsonl"
    log_path.write_text(
        '{"event": "ok", "n": 1}\n'
        "\n"
        '{"event": "ok", "n": 2}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(se, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        se.main()
    out = buf.getvalue()
    assert "✅ PASS" in out
    assert "2件" in out
