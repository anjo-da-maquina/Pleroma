import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "hook_test_suite_hash_log - 要件改ざん防止（コミットメント）: テストスイート(tests/)全体のハッシュを 記録し、前回実行時と比較して変更の有無を可視化する（タンパー・エビデンス）。"


# 要件改ざん防止（コミットメント）: テストスイート(tests/)全体のハッシュを
# 記録し、前回実行時と比較して変更の有無を可視化する（タンパー・エビデンス）。
# テストは正当な理由で変更され得るため、これは常に合格するログ出力ステップ
# であり、変更があった事実を見える形にすることが目的。
def main():
    current_hash = sha256_of_dir(ROOT / "tests")
    previous = load_state("hook_test_suite_hash_log")
    save_state("hook_test_suite_hash_log", {"hash": current_hash, "ts": __import__("time").time()})
    if previous and previous["hash"] != current_hash:
        report_info(NAME, f"テストスイートのコミットメントが変化しました: {previous['hash'][:12]}... -> {current_hash[:12]}...")
    else:
        report_info(NAME, f"テストスイートのコミットメント: {current_hash[:12]}... (変更なし)")
    report_pass(NAME, "要件(テストスイート)のコミットメントを記録しました。")

if __name__ == "__main__":
    main()
