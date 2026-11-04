import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_detection_layer_consensus - マルチLLM異端検知（簡易版）: 単一LLM(Ollama)の判定のみに依存する設計になって いないか、すなわち危険判定が複数の独立した検査レイヤー…"


# マルチLLM異端検知（簡易版）: 単一LLM(Ollama)の判定のみに依存する設計になって
# いないか、すなわち危険判定が複数の独立した検査レイヤー（静的AST + 動的フック）
# の合意で成立しているかを検証する。
def main():
    code = "import os; os.system('echo hacked')"
    static_caught = inquisition_catches(code)
    dynamic_blocked, _ = run_code_against_sefer(code)
    if not (static_caught and dynamic_blocked):
        report_fail(NAME, f"単一レイヤーのみに依存しています（静的={static_caught}, 動的={dynamic_blocked}）。多層防御の合意が取れていません。")
    report_pass(NAME, "静的解析・動的フックの双方が独立して合意し、危険コードを検知しました。")

if __name__ == "__main__":
    main()
