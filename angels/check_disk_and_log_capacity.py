import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "check_disk_and_log_capacity - 物理空間監査: ディスク空き容量と監査ログのサイズが許容範囲内であることを検証する。"


# 物理空間監査: ディスク空き容量と監査ログのサイズが許容範囲内であることを検証する。
import shutil

MAX_AUDIT_LOG_MB = 100

def main():
    total, used, free = shutil.disk_usage(str(ROOT))
    free_mb = free / (1024 * 1024)
    if free_mb < 50:
        report_fail(NAME, f"ディスク空き容量が危険域です: {free_mb:.1f}MB")

    log_path = ROOT / "sefer" / "audit_chain.jsonl"
    if log_path.exists():
        size_mb = log_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_AUDIT_LOG_MB:
            report_fail(NAME, f"監査ログが肥大化しています({size_mb:.1f}MB > {MAX_AUDIT_LOG_MB}MB)。ローテーションを検討してください。")

    report_pass(NAME, f"ディスク空き容量 {free_mb:.1f}MB、監査ログサイズは許容範囲内です。")

if __name__ == "__main__":
    main()
