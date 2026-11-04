import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_ledger_schema - スマートコントラクト監査: raziel_ledger.json のスキーマと、禁止イベント名が 妥当なPython audit event名の形式であるこ…"


# スマートコントラクト監査: raziel_ledger.json のスキーマと、禁止イベント名が
# 妥当なPython audit event名の形式であることを検証する（データ汚染検知）。
def main():
    ledger = load_json("sefer/raziel_ledger.json")
    if ledger is None or "banned_events" not in ledger:
        report_fail(NAME, "raziel_ledger.json が存在しない、または banned_events キーがありません。")
    events = ledger["banned_events"]
    if not isinstance(events, list) or not events:
        report_fail(NAME, "banned_events が空、または不正な形式です。")
    malformed = [e for e in events if not isinstance(e, str) or not VALID_EVENT_NAME_RE.match(e)]
    if malformed:
        report_fail(NAME, f"不正な形式のイベント名を検知しました（LLM幻覚の疑い）: {malformed}")

    pending = load_json("sefer/raziel_ledger_pending.json") or []
    bad_status = [p for p in pending if p.get("status") not in {"PENDING_HUMAN_REVIEW", "APPROVED", "REJECTED"}]
    if bad_status:
        report_fail(NAME, f"承認待ちキューに不正なstatusのエントリがあります: {bad_status}")

    report_pass(NAME, f"{len(events)}件の禁止イベント・{len(pending)}件の承認待ち提案を検証しました。")

if __name__ == "__main__":
    main()
