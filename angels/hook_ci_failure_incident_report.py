import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_info, save_state, ROOT

NAME = "hook_ci_failure_incident_report - 失敗時専用フック: CI失敗・キャンセルの実インシデントを記録する。"

# 失敗時専用フック: CI失敗・キャンセルの実インシデントを記録する。
# 以前は演出のためのprintのみで、実際の記録は一切残していなかった。


def main():
    incident = {
        "timestamp": __import__("time").time(),
        "github_run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "github_workflow": os.getenv("GITHUB_WORKFLOW", "unknown"),
        "trigger": "failure_or_cancelled",
    }
    report_path = ROOT / "sefer" / "incident_report.json"
    existing = []
    if report_path.exists():
        import json
        existing = json.loads(report_path.read_text(encoding="utf-8"))
    existing.append(incident)
    import json
    report_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    report_info(NAME, f"インシデントを sefer/incident_report.json に記録しました（累計{len(existing)}件）。")


if __name__ == "__main__":
    main()
