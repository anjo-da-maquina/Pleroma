import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_dependency_version_pinning - 依存関係監査: requirements.txt の全依存がバージョン固定(==)されているかを検証する (サプライチェーン攻撃対策の基本)。"


# 依存関係監査: requirements.txt の全依存がバージョン固定(==)されているかを検証する
# (サプライチェーン攻撃対策の基本)。
def main():
    req_path = ROOT / "requirements.txt"
    if not req_path.exists():
        report_fail(NAME, "requirements.txt が見つかりません。")
    unpinned = []
    for line in req_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            unpinned.append(line)
    if unpinned:
        report_fail(NAME, f"バージョン未固定の依存を検知しました: {unpinned}")
    report_pass(NAME, "全ての依存パッケージがバージョン固定(==)されています。")

if __name__ == "__main__":
    main()
