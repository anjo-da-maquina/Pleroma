import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "check_audit_hook_active (Surveyor) - ランタイム監視監査: sys.addaudithook によるMichael's Swordが 実際に登録されていることを検証する…"


# ランタイム監視監査: sys.addaudithook によるMichael's Swordが
# 実際に登録されていることを検証する（監視そのものの健全性チェック）。
def main():
    sys.path.insert(0, str(ROOT))
    import sefer
    # awaken()が一度でも呼ばれていれば、_michael_absolute_defense がフックされているはず。
    # 直接確認する手段がCPythonには無いため、実際に遮断が機能することで間接的に検証する。
    blocked, _ = run_code_against_sefer("import os; os.system('echo canary')")
    if not blocked:
        report_fail(NAME, "ランタイム監視(audit hook)が機能していません。致命的です。")
    report_pass(NAME, "ランタイム監視(sys.addaudithook)が正常に機能していることを確認しました。")

if __name__ == "__main__":
    main()
