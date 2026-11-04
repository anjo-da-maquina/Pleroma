import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "check_static_analysis_performance - 非機能要件（負荷）監査: inquisition()の静的解析が、大きめの入力に対しても 妥当な時間内に完了することを検証する（性能劣化の回帰防止）。"


# 非機能要件（負荷）監査: inquisition()の静的解析が、大きめの入力に対しても
# 妥当な時間内に完了することを検証する（性能劣化の回帰防止）。
import time

MAX_SECONDS = 5.0

def main():
    sys.path.insert(0, str(ROOT))
    from sefer import inquisition
    big_code = "\n".join([f"x{i} = {i}" for i in range(5000)])
    start = time.time()
    inquisition(big_code)
    elapsed = time.time() - start
    if elapsed > MAX_SECONDS:
        report_fail(NAME, f"静的解析が{elapsed:.2f}秒かかりました（閾値{MAX_SECONDS}秒を超過）。性能劣化の疑い。")
    report_pass(NAME, f"5000行相当のコードを{elapsed:.3f}秒で解析完了（閾値内）。")

if __name__ == "__main__":
    main()
