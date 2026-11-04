"""
tests/test_check_disk_and_log_capacity.py
=====================================
[新設 2026-11] angels/check_disk_and_log_capacity.py の単体テスト。

本天使(「ラグエルの天秤」)は、(1)ディスク空き容量が危険域
(50MB未満)でないこと、(2)監査証跡(`sefer/audit_chain.jsonl`)の
サイズが許容範囲(`MAX_AUDIT_LOG_MB`=100MB)を超えていないこと、を
検証する(物理空間監査)。天使群のテストカバレッジの棚卸しの過程で、
専用テストが一件も存在しないことが判明した。

`main()`は`shutil.disk_usage`をモジュールレベルで直接呼ぶため、
`check_disk_and_log_capacity.shutil.disk_usage`をmonkeypatchし、`ROOT`も一時
ディレクトリへmonkeypatchして監査ログファイルのサイズを制御する。
"""
import sys
from pathlib import Path
from collections import namedtuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import check_disk_and_log_capacity as rs

_DiskUsage = namedtuple("usage", ["total", "used", "free"])
MB = 1024 * 1024


def _patch_disk_usage(monkeypatch, free_mb):
    monkeypatch.setattr(
        rs.shutil, "disk_usage", lambda path: _DiskUsage(1000 * MB, 500 * MB, int(free_mb * MB))
    )


def test_real_repository_passes():
    """[実機の裏付け] 現時点の実行環境では、ディスク空き容量・監査ログ
    サイズともに許容範囲内であるため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rs.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_disk_space_is_critically_low(monkeypatch, tmp_path):
    """[核心] ディスク空き容量が50MB未満の危険域の場合、正しくFAILする。"""
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    _patch_disk_usage(monkeypatch, free_mb=10)
    try:
        rs.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_audit_log_exceeds_size_limit(monkeypatch, tmp_path):
    """[核心・監査ログ肥大化の検知] ディスク空き容量は十分でも、監査ログ
    (audit_chain.jsonl)が許容サイズ(100MB)を超えている場合、正しく
    FAILする。"""
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    _patch_disk_usage(monkeypatch, free_mb=500)
    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    log_path = sefer_dir / "audit_chain.jsonl"
    with open(log_path, "wb") as f:
        f.seek(int((rs.MAX_AUDIT_LOG_MB + 1) * MB) - 1)
        f.write(b"\0")
    try:
        rs.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_audit_log_is_absent(monkeypatch, tmp_path):
    """監査ログファイル自体が存在しない場合、サイズチェック自体がスキップ
    され、ディスク空き容量が十分であれば正しくPASSする。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(rs, "ROOT", tmp_path)
    _patch_disk_usage(monkeypatch, free_mb=500)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rs.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_when_audit_log_is_within_size_limit(monkeypatch, tmp_path):
    """監査ログが許容サイズ内であれば、想定どおりPASSする(回帰防止の
    ための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(rs, "ROOT", tmp_path)
    _patch_disk_usage(monkeypatch, free_mb=500)
    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    (sefer_dir / "audit_chain.jsonl").write_text('{"event": "x"}\n', encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rs.main()
    assert "✅ PASS" in buf.getvalue()
