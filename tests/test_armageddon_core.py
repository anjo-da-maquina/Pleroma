"""
[テスト追加 2026-10] tartarus/armageddon_core.py の純粋ロジックに対する回帰テスト。

armageddon.py 本体はMACアドレスゲートにより創造主のローカル環境以外では
起動しないため、ゲートに依存しない armageddon_core.py を直接テストする。
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tartarus"))
import armageddon_core as core

PLEROMA_ROOT = Path(__file__).resolve().parent.parent


def test_extract_python_code_with_fence():
    text = "ここにコードがあります:\n```python\nprint('hi')\n```\n以上です。"
    assert core.extract_python_code(text) == "print('hi')"


def test_extract_python_code_without_fence_strips_backticks():
    text = "```print('hi')```"
    assert "```" not in core.extract_python_code(text)


def test_validate_banned_event_accepts_well_formed_name():
    ok, reason = core.validate_banned_event("os.popen2")
    assert ok is True


def test_validate_banned_event_rejects_critical_infrastructure():
    for critical in ["open", "exec", "eval", "import", "compile"]:
        ok, reason = core.validate_banned_event(critical)
        assert ok is False, f"'{critical}' は自己免疫疾患ガードで拒否されるべき"
        assert "self-immunity" in reason or "cannot be banned" in reason


def test_validate_banned_event_rejects_malformed_hallucination():
    """LLMの幻覚を模した、audit event名として不正な出力を拒否できるか。"""
    hallucinated_outputs = [
        "",
        "この関数は危険です",  # 自然文（説明を拒否できなかったケース）
        "rm -rf /",            # シェルコマンドを誤出力したケース
        "os",                  # ドット区切りがない
        "DROP TABLE users;",
    ]
    for bad in hallucinated_outputs:
        ok, reason = core.validate_banned_event(bad)
        assert ok is False, f"幻覚的な出力 {bad!r} を誤って受理してしまいました"


def test_apply_new_seal_queues_pending_not_live_ledger(tmp_path: Path):
    ledger_path = tmp_path / "raziel_ledger.json"
    pending_path = tmp_path / "raziel_ledger_pending.json"
    ledger_path.write_text(json.dumps({"banned_events": ["os.system"]}), encoding="utf-8")

    result = core.apply_new_seal(
        "os.popen2", attack_code="import os; os.popen2('x')", source_error="bypass",
        ledger_path=ledger_path, pending_path=pending_path,
    )
    assert result is True

    # 実際の禁止リストは変化しない（人間承認を経るまで）
    live = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert "os.popen2" not in live["banned_events"]

    # 承認待ちキューに積まれている
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    assert len(pending) == 1
    assert pending[0]["event"] == "os.popen2"
    assert pending[0]["status"] == "PENDING_HUMAN_REVIEW"


def test_apply_new_seal_rejects_duplicate_already_live(tmp_path: Path):
    ledger_path = tmp_path / "raziel_ledger.json"
    pending_path = tmp_path / "raziel_ledger_pending.json"
    ledger_path.write_text(json.dumps({"banned_events": ["os.system"]}), encoding="utf-8")

    result = core.apply_new_seal("os.system", ledger_path=ledger_path, pending_path=pending_path)
    assert result is False  # 既に本採用済みのため提案不要


def test_apply_new_seal_rejects_duplicate_already_pending(tmp_path: Path):
    ledger_path = tmp_path / "raziel_ledger.json"
    pending_path = tmp_path / "raziel_ledger_pending.json"
    ledger_path.write_text(json.dumps({"banned_events": []}), encoding="utf-8")

    first = core.apply_new_seal("os.popen2", ledger_path=ledger_path, pending_path=pending_path)
    second = core.apply_new_seal("os.popen2", ledger_path=ledger_path, pending_path=pending_path)
    assert first is True
    assert second is False  # 二重提案を防ぐ

    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    assert len(pending) == 1


def test_record_to_akashic_and_initialize_arena(tmp_path: Path):
    akashic_path = tmp_path / "akashic_records.json"
    core.record_to_akashic(1, " payload ", "Failed", "err", 3, "hint", akashic_path=akashic_path)
    records = json.loads(akashic_path.read_text(encoding="utf-8"))
    assert len(records) == 1
    assert records[0]["payload"] == "payload"  # strip()されていること
    assert records[0]["generation"] == 1

    purged = core.initialize_arena(akashic_path=akashic_path)
    assert purged is True
    assert not akashic_path.exists()

    purged_again = core.initialize_arena(akashic_path=akashic_path)
    assert purged_again is False


def test_build_forge_script_actually_blocks_hard_denied_event(tmp_path):
    """[脆弱性修正の核心] GRIMOIRE.md §AU参照。以前は生成スクリプトが
    `awaken()`のみを呼び`with Sanctum(...):`に入らなかったため、
    `os.system`のような単純な(難読化すら無い)攻撃すら遮断されず、
    闘技場が実質的に空の防壁と戦っていた。本テストは、実際に生成
    スクリプトをサブプロセスとして実行し、`os.system`が本当に遮断され、
    かつ対象のマーカーファイルが作成されないことを実機で確認する。"""
    payload = "import os\nos.system('echo blocked_test_marker')\n"

    script = core.build_forge_script(payload, PLEROMA_ROOT, tmp_path)
    script_path = tmp_path / "temp_mutation.py"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script_path)], cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        "os.system を使った攻撃ペイロードが遮断されず正常終了してしまった"
        "(with Sanctum(...)が機能していない可能性)"
    )
    assert "LossOfAtaraxia" in result.stderr and "os.system" in result.stderr, (
        f"期待した遮断メッセージが出力されていません: {result.stderr!r}"
    )


def test_build_forge_script_still_allows_legitimate_write_within_tartarus_dir(tmp_path):
    """[回帰防止] 正規の(禁止操作を使わない)ファイル書き込みは、
    allowed_dirs(闘技場ディレクトリ)内であれば引き続き成功すること。
    §AUの修正がSanctumを正しく機能させつつ、過剰検知で全てを
    遮断してしまってもいないことを固定する。"""
    payload = "with open('lucifer_victory.txt', 'w', encoding='utf-8') as f:\n    f.write('pwned')\n"

    script = core.build_forge_script(payload, PLEROMA_ROOT, tmp_path)
    script_path = tmp_path / "temp_mutation.py"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script_path)], cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert result.returncode == 0, f"正規の書き込みが誤って遮断された: {result.stderr}"
    assert (tmp_path / "lucifer_victory.txt").exists()


def test_build_forge_script_escapes_payload_safely(tmp_path):
    """[回帰防止] ペイロードに引用符・バックスラッシュ・複数行の三重引用符
    文字列が含まれていても、生成スクリプトが構文的に壊れないこと。"""
    tricky_payload = (
        "s = \"\"\"multi\nline\ntriple quoted 'with' \\\"nested\\\" quotes\"\"\"\n"
        "assert 'multi' in s\n"
    )
    script = core.build_forge_script(tricky_payload, PLEROMA_ROOT, tmp_path)
    script_path = tmp_path / "temp_mutation.py"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script_path)], cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert result.returncode == 0, f"エスケープ処理が壊れている: {result.stderr}"
