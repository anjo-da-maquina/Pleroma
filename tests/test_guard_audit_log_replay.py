"""
tests/test_guard_audit_log_replay.py
=====================================
[新設 2026-11] angels/guard_audit_log_replay.py の単体テスト。

本天使(「ウリエルの灯」)は、監査証跡ファイル(`sefer/audit_chain.jsonl`)
内に同一ハッシュ(=同一イベントの再生、リプレイ攻撃)が重複して記録
されていないかを検証する。天使群のテストカバレッジの棚卸しの過程で、
専用テストが一件も存在しないことが判明した。

`main()`は`ROOT / "sefer" / "audit_chain.jsonl"`という固定パスを直接
参照するため、`guard_audit_log_replay.ROOT`をテストごとに一時ディレクトリへ
monkeypatchして検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import guard_audit_log_replay as un


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリの実際の監査証跡には重複ハッシュ
    が無いため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        un.main()
    assert "✅ PASS" in buf.getvalue()


def test_reports_not_applicable_when_chain_file_is_missing(monkeypatch, tmp_path):
    """監査チェーンファイル自体が存在しない場合は、PASSではなく
    NOT_APPLICABLEを報告する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(un, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        un.main()
    assert "⬜ NOT_APPLICABLE" in buf.getvalue()


def test_fails_when_duplicate_hash_is_present(monkeypatch, tmp_path):
    """[核心・リプレイ攻撃検知] 同一の`hash`値を持つエントリが2件以上
    存在する場合、本天使が正しくFAIL(sys.exit(1))することを確認する。"""
    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    log_path = sefer_dir / "audit_chain.jsonl"
    log_path.write_text(
        '{"index": 0, "hash": "aaa", "event": "e1"}\n'
        '{"index": 1, "hash": "bbb", "event": "e2"}\n'
        '{"index": 2, "hash": "aaa", "event": "e1-replayed"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(un, "ROOT", tmp_path)
    try:
        un.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_all_hashes_are_unique(monkeypatch, tmp_path):
    """全エントリのハッシュが一意であれば、想定どおりPASSする(回帰
    防止のための明示的な固定)。空行はスキップされることも確認する。"""
    import io
    from contextlib import redirect_stdout

    sefer_dir = tmp_path / "sefer"
    sefer_dir.mkdir()
    log_path = sefer_dir / "audit_chain.jsonl"
    log_path.write_text(
        '{"index": 0, "hash": "aaa", "event": "e1"}\n'
        "\n"
        '{"index": 1, "hash": "bbb", "event": "e2"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(un, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        un.main()
    out = buf.getvalue()
    assert "✅ PASS" in out
    assert "2件" in out
