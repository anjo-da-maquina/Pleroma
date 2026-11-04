import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_blocklist_regression (Cartographer) - 意味論的ドリフト検知: Gabrielの禁止モジュール/関数リストが、 既知のベースラインより弱体化（縮小）していないかを検証する。"


# 意味論的ドリフト検知: Gabrielの禁止モジュール/関数リストが、
# 既知のベースラインより弱体化（縮小）していないかを検証する。
BASELINE_FORBIDDEN_MODULES = {"pickle", "ctypes", "importlib", "socket", "urllib", "requests", "http", "subprocess", "os"}
BASELINE_FORBIDDEN_FUNCS = {"__import__", "getattr", "eval", "exec", "compile", "os.system", "subprocess.Popen"}

def main():
    sys.path.insert(0, str(ROOT))
    import sefer
    import inspect
    src = inspect.getsource(sefer.inquisition)
    missing_modules = [m for m in BASELINE_FORBIDDEN_MODULES if f'"{m}"' not in src and f"'{m}'" not in src]
    missing_funcs = [fn for fn in BASELINE_FORBIDDEN_FUNCS if f'"{fn}"' not in src and f"'{fn}'" not in src]
    if missing_modules or missing_funcs:
        report_fail(NAME, f"Gabrielの検査基準が弱体化しています。欠落モジュール={missing_modules} 欠落関数={missing_funcs}")
    report_pass(NAME, "Gabrielの禁止リストはベースラインから弱体化していません。")

if __name__ == "__main__":
    main()
