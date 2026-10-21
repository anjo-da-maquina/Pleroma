import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "サンダルフォンの響き (Sandalphon Echo)"


# 監査証跡監査: 監査チェーンファイル自体の存在・可読性・JSONL形式の妥当性を検証する。
def main():
    log_path = ROOT / "sefer" / "audit_chain.jsonl"
    if not log_path.exists():
        report_not_applicable(NAME, "監査チェーン未生成のため検査対象なし(違反が一度も記録されていないのか、チェーン自体が初期化されていないのかは本検査では判別できない)。")
        return
    import json as _json
    bad_lines = 0
    total = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            total += 1
            try:
                _json.loads(line)
            except Exception:
                bad_lines += 1
    if bad_lines:
        report_fail(NAME, f"監査証跡に{bad_lines}/{total}件のJSONLパース不能な行があります。")
    report_pass(NAME, f"{total}件の監査証跡エントリが全て正しいJSONL形式であることを確認しました。")

if __name__ == "__main__":
    main()
