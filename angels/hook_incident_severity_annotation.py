import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_info, ROOT

NAME = "hook_incident_severity_annotation (Custodian) - 失敗時専用フック: CI失敗を「要件定義違反」として incident_report.json に 要約行を追記する…"

# 失敗時専用フック: CI失敗を「要件定義違反」として incident_report.json に
# 要約行を追記する（以前はprintのみで記録が残らなかった）。


def main():
    report_path = ROOT / "sefer" / "incident_report.json"
    if report_path.exists():
        import json
        incidents = json.loads(report_path.read_text(encoding="utf-8"))
        if incidents:
            incidents[-1]["severity"] = "CRITICAL_REQUIREMENTS_VIOLATION"
            report_path.write_text(json.dumps(incidents, indent=2, ensure_ascii=False), encoding="utf-8")
    report_info(NAME, "直近のインシデントに重大度 CRITICAL_REQUIREMENTS_VIOLATION を付与しました。")


if __name__ == "__main__":
    main()
