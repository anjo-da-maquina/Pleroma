import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "サリエルの監視 (Sariel Fallen Auditor)"


# 外部ツール監査: adapters/ 配下のスクリプトが禁止モジュールを
# 直接importしていないかをGabrielの静的解析で検証する。
def main():
    adapters_dir = ROOT / "adapters"
    if not adapters_dir.exists():
        report_not_applicable(NAME, "adapters/ が存在しないため検査対象なし。")
        return
    violations = {}
    for p in adapters_dir.glob("*.py"):
        code = p.read_text(encoding="utf-8-sig", errors="ignore")  # BOM付きファイルに対応
        sys.path.insert(0, str(ROOT))
        from sefer import inquisition
        findings = inquisition(code)
        critical = [f for f in findings if f.severity == "critical"]
        if critical:
            violations[p.name] = [f.message for f in critical]
    if violations:
        report_fail(NAME, f"外部アダプタに重大な静的解析違反を検知しました: {violations}")
    report_pass(NAME, "外部アダプタ(adapters/)に重大な静的解析違反は検出されませんでした。")

if __name__ == "__main__":
    main()
