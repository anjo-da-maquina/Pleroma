import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "ウリエルの灯 (Uriel Nonce)"


# リプレイ攻撃監視: 監査チェーン内に同一ハッシュ(=同一イベントの再生)が
# 重複していないかを検証する。
def main():
    log_path = ROOT / "sefer" / "audit_chain.jsonl"
    if not log_path.exists():
        report_not_applicable(NAME, "監査チェーンが未生成のため検査対象なし。")
        return
    seen = {}
    dupes = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            import json as _json
            entry = _json.loads(line)
            h = entry.get("hash")
            if h in seen:
                dupes.append(h)
            seen[h] = entry.get("index")
    if dupes:
        report_fail(NAME, f"リプレイ攻撃の疑い: 重複ハッシュを検知しました: {dupes}")
    report_pass(NAME, f"{len(seen)}件のログエントリにリプレイ（重複）は検知されませんでした。")

if __name__ == "__main__":
    main()
