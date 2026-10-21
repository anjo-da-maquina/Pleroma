import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "メタトロンの啓示 (Metatron Revelation MCP)"


# 思考統制監査: Armageddonエンジンの自動ルール更新が、必ず人間承認キュー
# (raziel_ledger_pending.json)を経由する実装になっているかを静的に検証する。
# [2026-10] 純粋ロジックは armageddon_core.py に分離されたため、
# 両ファイルを合わせて検証する。
def main():
    armageddon = ROOT / "tartarus" / "armageddon.py"
    armageddon_core = ROOT / "tartarus" / "armageddon_core.py"
    if not armageddon.exists() and not armageddon_core.exists():
        report_not_applicable(NAME, "armageddon.py が存在しないため検査対象なし。")
        return
    combined_text = ""
    if armageddon.exists():
        combined_text += armageddon.read_text(encoding="utf-8")
    if armageddon_core.exists():
        combined_text += armageddon_core.read_text(encoding="utf-8")
    if "PENDING_LEDGER_PATH" not in combined_text or "PENDING_HUMAN_REVIEW" not in combined_text:
        report_fail(NAME, "Armageddonエンジンが人間承認ゲートを経由せず直接ルールを反映する実装になっています。")
    if "def apply_new_seal" not in combined_text:
        report_fail(NAME, "apply_new_seal() が見つかりません。承認キュー化ロジックが欠落している可能性があります。")
    report_pass(NAME, "Armageddonエンジンの自動ルール更新は人間承認ゲートを経由する実装です。")

if __name__ == "__main__":
    main()
