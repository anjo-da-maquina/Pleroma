"""
tests/test_virtues_load.py
=====================================
[新設 2026-11] angels/virtues_load.py の単体テスト。

本天使(「力天使の試練」)は、`sefer.inquisition()`の静的解析が、大きめ
の入力(5000行相当)に対しても`MAX_SECONDS`秒以内に完了することを
検証する(性能劣化の回帰防止)。天使群のテストカバレッジの棚卸しの
過程で、専用テストが一件も存在しないことが判明した。

FAIL分岐を再現するために、実際に5秒以上かかる処理を発生させる代わりに
`virtues_load.MAX_SECONDS`を一時的に極小値(0秒未満)へmonkeypatchし、
実際の解析時間が常にその閾値を超えるようにする。これにより、CI実行
時間を不必要に延ばさずに、FAIL分岐の判定ロジック自体を確実に検証
できる。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import virtues_load as vl


def test_real_repository_passes():
    """[実機の裏付け] 現時点の実装では、5000行相当のコードの静的解析が
    閾値内で完了するため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        vl.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_elapsed_time_exceeds_threshold(monkeypatch):
    """[核心・性能劣化回帰の検知] 解析時間が`MAX_SECONDS`を超えた場合、
    本天使が正しくFAIL(sys.exit(1))することを確認する。実際に処理を
    遅延させる代わりに、閾値自体を実行時間より確実に小さい値
    (-1秒)へ一時的に差し替えることで、CI実行時間を延ばさずに
    この分岐を再現する。"""
    monkeypatch.setattr(vl, "MAX_SECONDS", -1.0)
    try:
        vl.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_threshold_is_generous(monkeypatch):
    """閾値が十分に大きい場合は、想定どおりPASSする(回帰防止のための
    明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(vl, "MAX_SECONDS", 3600.0)
    buf = io.StringIO()
    with redirect_stdout(buf):
        vl.main()
    assert "✅ PASS" in buf.getvalue()
