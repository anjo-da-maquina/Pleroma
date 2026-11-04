import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_banned_events_baseline - 分散型オラクル真理監査: raziel_ledger.json のベースライン禁止イベントが 欠落・改変されていないかを検証する…"


# 分散型オラクル真理監査: raziel_ledger.json のベースライン禁止イベントが
# 欠落・改変されていないかを検証する（オラクルの「真実性」チェック）。
BASELINE_EVENTS = {"os.system", "subprocess.Popen", "os.remove"}

def main():
    ledger = load_json("sefer/raziel_ledger.json")
    if ledger is None:
        report_fail(NAME, "raziel_ledger.json が存在しません。")
    missing = BASELINE_EVENTS - set(ledger.get("banned_events", []))
    if missing:
        report_fail(NAME, f"ベースラインの禁止イベントが欠落しています: {missing}")
    report_pass(NAME, "オラクル（Raziel's Ledger）のベースライン真実性を確認しました。")

if __name__ == "__main__":
    main()
