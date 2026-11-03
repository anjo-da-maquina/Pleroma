"""
tests/test_enochian_oracle.py
=====================================
[新設 2026-11] angels/enochian_oracle.py の単体テスト。

本天使(「エノク語の神託」)は、分散型オラクル台帳(`sefer/raziel_ledger.json`)
のベースライン禁止イベント(`os.system`・`subprocess.Popen`・`os.remove`)
が欠落・改変されていないかを検証する(オラクルの「真実性」チェック)。
天使群のテストカバレッジの棚卸しの過程で、専用テストが一件も存在しない
ことが判明した。

`load_json`は`_common.ROOT`を閉じた状態で`sefer/raziel_ledger.json`を
直接読むため、`enochian_oracle.load_json`自体をモジュールレベルで
monkeypatchして、実際のファイルI/Oを介さずに判定ロジックのみを検証
する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import enochian_oracle as eo


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリのraziel_ledger.jsonには、
    ベースライン禁止イベントが全て含まれているため、本天使はPASSを
    報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        eo.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_ledger_is_missing(monkeypatch):
    """raziel_ledger.json自体が存在しない(load_jsonがNoneを返す)場合、
    正しくFAILする。"""
    monkeypatch.setattr(eo, "load_json", lambda path: None)
    try:
        eo.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_one_baseline_event_is_missing(monkeypatch):
    """[核心・真実性破りの検知] ベースライン禁止イベントのうち1件
    (例: os.system)が台帳から欠落している場合、正しくFAILする。"""
    monkeypatch.setattr(
        eo, "load_json", lambda path: {"banned_events": ["subprocess.Popen", "os.remove"]}
    )
    try:
        eo.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_banned_events_key_is_absent(monkeypatch):
    """`banned_events`キー自体が台帳JSONに存在しない場合も、正しく
    FAILする(空集合扱いとなり、全ベースラインが欠落と判定される)。"""
    monkeypatch.setattr(eo, "load_json", lambda path: {})
    try:
        eo.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_ledger_has_extra_events_beyond_baseline(monkeypatch):
    """台帳にベースライン以外の追加の禁止イベントが含まれていても、
    ベースライン自体を全て満たしていれば正しくPASSする(回帰防止の
    ための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(
        eo,
        "load_json",
        lambda path: {
            "banned_events": ["os.system", "subprocess.Popen", "os.remove", "os.chmod"]
        },
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        eo.main()
    assert "✅ PASS" in buf.getvalue()
