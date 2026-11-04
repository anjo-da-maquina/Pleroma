import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_signed_chain_integrity - 状態遷移監査: 署名付き監査チェーン(audit_chain.jsonl)のハッシュ連鎖が 改ざんされていないことを検証する。"


# 状態遷移監査: 署名付き監査チェーン(audit_chain.jsonl)のハッシュ連鎖が
# 改ざんされていないことを検証する。
def main():
    sys.path.insert(0, str(ROOT))
    from sefer.audit_chain import SignedAuditChain
    chain = SignedAuditChain(log_path=str(ROOT / "sefer" / "audit_chain.jsonl"))
    if not chain.verify_integrity():
        report_fail(NAME, "監査チェーンのハッシュ連鎖が破壊されています（改ざんの疑い）。")
    report_pass(NAME, "監査チェーンのハッシュ連鎖の整合性を確認しました。")

if __name__ == "__main__":
    main()
