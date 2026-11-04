import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_info, ROOT

NAME = "hook_incident_kill_switch_flag (Courier) - 失敗時専用フック: 連座制キルスイッチ。"

# 失敗時専用フック: 連座制キルスイッチ。実際に外部接続を遮断する手段は
# このCI環境には存在しないため、「遮断すべきだった」という事実を
# incident_report.json に明示的に記録する（演出のみで終わらせない）。


def main():
    report_path = ROOT / "sefer" / "incident_report.json"
    if report_path.exists():
        import json
        incidents = json.loads(report_path.read_text(encoding="utf-8"))
        if incidents:
            incidents[-1]["kill_switch_recommended"] = True
            report_path.write_text(json.dumps(incidents, indent=2, ensure_ascii=False), encoding="utf-8")
    report_info(NAME, "キルスイッチ推奨フラグを記録しました。実際の遮断は人間の確認後に実施してください。")


if __name__ == "__main__":
    main()
