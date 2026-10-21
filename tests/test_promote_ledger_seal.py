"""
tests/test_promote_ledger_seal.py
===================================
[新設 2026-10 §BZ] tools/promote_ledger_seal.py の list_pending() が、
過去に拒否(REJECTED)された事件名の再提案であることを、審査者に対して
正しく警告表示することを確認する回帰テスト。

背景: tartarus/armageddon_core.apply_new_seal() の重複防止チェックを
「現在も承認待ちの提案のみ」に限定した結果(§BZ)、過去にREJECTEDとなった
事件名でも、新たな実証を伴えば再提案されるようになった。審査者がその
経緯(=これは過去に一度拒否したはずの事件名である)を知らないまま
判断してしまうことを防ぐため、list_pending()はprior_rejection_countを
明示的に表示しなければならない。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import promote_ledger_seal as pls


def test_list_pending_warns_about_reproposal_after_past_rejection(tmp_path, monkeypatch, capsys):
    pending_path = tmp_path / "raziel_ledger_pending.json"
    pending_path.write_text(json.dumps([
        {
            "event": "os.popen2",
            "proposed_at": "2026-10-21T00:00:00",
            "attack_code_excerpt": "import os; os.popen2('x')",
            "source_error_excerpt": "bypass",
            "status": "PENDING_HUMAN_REVIEW",
            "prior_rejection_count": 2,
        }
    ]), encoding="utf-8")
    monkeypatch.setattr(pls, "PENDING_LEDGER_PATH", pending_path)

    pls.list_pending()
    out = capsys.readouterr().out

    assert "os.popen2" in out
    assert "過去に2回拒否されています" in out, (
        "過去に拒否された事件名の再提案であることが、審査者に警告されていない"
        "(§BZの回帰: 拒否の経緯を知らないまま判断してしまう恐れ)"
    )


def test_list_pending_shows_no_warning_for_a_first_time_proposal(tmp_path, monkeypatch, capsys):
    """[誤検知防止] 一度も拒否されていない通常の新規提案には、
    再提案の警告が表示されてはならない。"""
    pending_path = tmp_path / "raziel_ledger_pending.json"
    pending_path.write_text(json.dumps([
        {
            "event": "subprocess.Popen",
            "proposed_at": "2026-10-21T00:00:00",
            "attack_code_excerpt": "x",
            "source_error_excerpt": "y",
            "status": "PENDING_HUMAN_REVIEW",
            "prior_rejection_count": 0,
        }
    ]), encoding="utf-8")
    monkeypatch.setattr(pls, "PENDING_LEDGER_PATH", pending_path)

    pls.list_pending()
    out = capsys.readouterr().out

    assert "注意" not in out


def test_list_pending_handles_entries_without_prior_rejection_count_field(tmp_path, monkeypatch, capsys):
    """[後方互換性] §BZ以前に作られた、prior_rejection_countフィールドを
    持たない古い提案エントリでも、list_pending()が例外を発生させずに
    動作することを確認する(dict.getの既定値0により警告無しで表示される)。"""
    pending_path = tmp_path / "raziel_ledger_pending.json"
    pending_path.write_text(json.dumps([
        {
            "event": "legacy.event",
            "proposed_at": "2026-01-01T00:00:00",
            "attack_code_excerpt": "x",
            "source_error_excerpt": "y",
            "status": "PENDING_HUMAN_REVIEW",
        }
    ]), encoding="utf-8")
    monkeypatch.setattr(pls, "PENDING_LEDGER_PATH", pending_path)

    pls.list_pending()
    out = capsys.readouterr().out
    assert "legacy.event" in out
    assert "注意" not in out


def test_list_pending_handles_no_open_items(tmp_path, monkeypatch, capsys):
    pending_path = tmp_path / "raziel_ledger_pending.json"
    pending_path.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setattr(pls, "PENDING_LEDGER_PATH", pending_path)

    pls.list_pending()
    out = capsys.readouterr().out
    assert "承認待ちの提案はありません。" in out
