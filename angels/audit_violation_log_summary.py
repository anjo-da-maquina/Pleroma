import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_violation_log_summary (Loremaster) - 品質保持証跡一覧出力: これまでに記録された監査違反の件数・種別を集計し、 可読なマニフェストとして出力する。"


# 品質保持証跡一覧出力: これまでに記録された監査違反の件数・種別を集計し、
# 可読なマニフェストとして出力する。
def main():
    log_path = ROOT / "sefer" / "audit_chain.jsonl"
    manifest = {"total_violations": 0, "by_event": {}}
    if log_path.exists():
        import json as _json
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = _json.loads(line)
                manifest["total_violations"] += 1
                ev = entry.get("event", "unknown")
                manifest["by_event"][ev] = manifest["by_event"].get(ev, 0) + 1
    manifest_path = ROOT / "sefer" / "audit_violation_log_summary.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        import json as _json
        _json.dump(manifest, f, indent=2, ensure_ascii=False)
    report_pass(NAME, f"品質保持マニフェストを出力しました（累計違反検知数: {manifest['total_violations']}件）。")

if __name__ == "__main__":
    main()
