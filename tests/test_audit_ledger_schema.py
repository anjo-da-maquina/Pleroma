"""
tests/test_audit_ledger_schema.py
=====================================
[新設 2026-11] angels/audit_ledger_schema.py の単体テスト。

本天使(「ラジエルの書」)は、`sefer/raziel_ledger.json`のスキーマと、
禁止イベント名が妥当なPython audit event名の形式であること(LLM幻覚に
よるデータ汚染検知)、および`sefer/raziel_ledger_pending.json`の各
エントリのstatusが既知の値であることを検証する。天使群のテスト
カバレッジの棚卸しの過程で、専用テストが一件も存在しないことが判明
した。

`main()`は共有ヘルパーの`load_json(relative_path)`を直接呼ぶため、
`audit_ledger_schema.load_json`をパスごとに異なる戻り値を返す偽の関数へ
monkeypatchして各分岐を検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import audit_ledger_schema as ra


def _fake_load_json(ledger=None, pending=None):
    """audit_ledger_schema.load_jsonを、パス文字列に応じて異なる戻り値を
    返す偽の関数に差し替えるためのヘルパー。"""
    def _fn(relative_path):
        if relative_path == "sefer/raziel_ledger.json":
            return ledger
        if relative_path == "sefer/raziel_ledger_pending.json":
            return pending
        raise AssertionError(f"想定外のパスで呼ばれました: {relative_path}")
    return _fn


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリの実際のraziel_ledger.jsonは
    妥当なスキーマであるため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        ra.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_ledger_file_is_missing(monkeypatch):
    """ledgerファイル自体が存在しない(load_jsonがNoneを返す)場合、
    正しくFAILする。"""
    monkeypatch.setattr(ra, "load_json", _fake_load_json(ledger=None, pending=[]))
    try:
        ra.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_banned_events_key_is_missing(monkeypatch):
    """ledgerに`banned_events`キー自体が無い場合、正しくFAILする。"""
    monkeypatch.setattr(ra, "load_json", _fake_load_json(ledger={}, pending=[]))
    try:
        ra.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_banned_events_is_empty(monkeypatch):
    """`banned_events`が空リストの場合、正しくFAILする(禁止イベントが
    一件も無い=保護が成立していない状態を、空という理由だけでPASSに
    しない)。"""
    monkeypatch.setattr(
        ra, "load_json", _fake_load_json(ledger={"banned_events": []}, pending=[]),
    )
    try:
        ra.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_event_name_is_malformed(monkeypatch):
    """[核心・LLM幻覚データ汚染の検知] `banned_events`に、妥当な
    `module.func`形式ではない文字列(例: 単語だけ、空文字列、ドットの
    無い名前)が混入している場合、正しくFAILすることを確認する。"""
    monkeypatch.setattr(
        ra, "load_json",
        _fake_load_json(
            ledger={"banned_events": ["os.system", "totally_not_a_real_event_name"]},
            pending=[],
        ),
    )
    try:
        ra.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_pending_entry_has_unknown_status(monkeypatch):
    """承認待ちキューのエントリに、既知の3状態
    (PENDING_HUMAN_REVIEW/APPROVED/REJECTED)以外のstatusが混入している
    場合、正しくFAILすることを確認する。"""
    monkeypatch.setattr(
        ra, "load_json",
        _fake_load_json(
            ledger={"banned_events": ["os.system"]},
            pending=[{"event": "os.system", "status": "SOMETHING_UNEXPECTED"}],
        ),
    )
    try:
        ra.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_with_valid_ledger_and_pending(monkeypatch):
    """妥当なledger・pendingの組み合わせでは、想定どおりPASSする
    (回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(
        ra, "load_json",
        _fake_load_json(
            ledger={"banned_events": ["os.system", "socket.connect"]},
            pending=[{"event": "os.fork", "status": "PENDING_HUMAN_REVIEW"}],
        ),
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        ra.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_when_pending_is_absent(monkeypatch):
    """承認待ちキューのファイル自体が存在しない(load_jsonがNoneを返す)
    場合でも、`or []`によって空扱いとなり正しくPASSすることを確認する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(
        ra, "load_json",
        _fake_load_json(ledger={"banned_events": ["os.system"]}, pending=None),
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        ra.main()
    assert "✅ PASS" in buf.getvalue()
