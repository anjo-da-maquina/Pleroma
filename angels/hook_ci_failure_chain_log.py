import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_info, ROOT

NAME = "hook_ci_failure_chain_log (Clerk) - 失敗時専用フック: インシデントの不変台帳への記録。"

# 失敗時専用フック: インシデントの不変台帳への記録。実際の外部分散ストレージ
# (IPFS/Arweave)への送信は本環境では行わず、ローカルの検証可能な
# ハッシュ台帳(sefer/audit_chain.jsonl)への追記で代替する。


def main():
    sys.path.insert(0, str(ROOT))
    from sefer import _log_violation_to_chain
    _log_violation_to_chain("CI_FAILURE_LEDGER", {
        "message": "CI失敗イベントを不変台帳に記録しました。",
        "github_run_id": os.getenv("GITHUB_RUN_ID", "local"),
    })
    report_info(NAME, "CI失敗イベントを sefer/audit_chain.jsonl（不変台帳）に記録しました。")


if __name__ == "__main__":
    main()
