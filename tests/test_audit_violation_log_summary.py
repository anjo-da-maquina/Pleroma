"""
tests/test_audit_violation_log_summary.py
=====================================
[新設 2026-11] angels/audit_violation_log_summary.py の単体テスト。

本天使(「大天使の印環」)は、これまでに記録された監査違反の件数・
種別を集計し、`sefer/audit_violation_log_summary.json`として出力する。報告系の
ステップであり`report_fail`は一切呼ばない(常にPASSを報告する設計)が、
集計ロジック自体(件数・イベント種別ごとの内訳・出力ファイルの妥当な
JSON形式)は、天使群のテストカバレッジの棚卸しの過程で、専用テストが
一件も存在しないことが判明した。

`main()`は`ROOT / "sefer" / "audit_chain.jsonl"`を読み、
`ROOT / "sefer" / "audit_violation_log_summary.json"`へ書き出すため、
`audit_violation_log_summary.ROOT`を一時ディレクトリへmonkeypatchして検証する。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import audit_violation_log_summary as sm


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリで実行すると、常にPASSを報告
    する(集計対象が無くても例外にならない設計のため)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        sm.main()
    assert "✅ PASS" in buf.getvalue()


def test_counts_violations_correctly_and_writes_valid_json(monkeypatch, tmp_path):
    """[核心] 監査証跡の各行を正しく集計し(総件数・イベント種別ごとの
    内訳)、妥当なJSONとして書き出すことを確認する。"""
    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    log_path = sefer_dir / "audit_chain.jsonl"
    log_path.write_text(
        '{"event": "socket.connect"}\n'
        '{"event": "os.system"}\n'
        '{"event": "socket.connect"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sm, "ROOT", tmp_path)

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        sm.main()
    assert "✅ PASS" in buf.getvalue()
    assert "3件" in buf.getvalue()

    manifest_path = tmp_path / "sefer" / "audit_violation_log_summary.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["total_violations"] == 3
    assert manifest["by_event"] == {"socket.connect": 2, "os.system": 1}


def test_handles_missing_chain_file_with_zero_counts(monkeypatch, tmp_path):
    """監査チェーンファイル自体が存在しない場合でも、例外を投げずに
    件数0のマニフェストを正しく出力することを確認する。"""
    monkeypatch.setattr(sm, "ROOT", tmp_path)
    (tmp_path / "sefer").mkdir()

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        sm.main()
    assert "✅ PASS" in buf.getvalue()
    assert "0件" in buf.getvalue()

    manifest_path = tmp_path / "sefer" / "audit_violation_log_summary.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["total_violations"] == 0
    assert manifest["by_event"] == {}
