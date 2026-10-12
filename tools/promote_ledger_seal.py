"""
Raziel's Ledger 承認プロモーションツール
=========================================
[脆弱性修正 2026-10] Armageddon Engine (Metatron) がLLM出力から提案した
新しい禁止イベントを、人間が内容を確認した上で raziel_ledger.json
（実際に有効な禁止リスト）へ昇格させるためのツール。

これにより、未検証のLLM出力（プロンプトインジェクション・幻覚を含む）が
そのまま実運用の防御ルールに反映されることを防ぐ。

使い方:
    python tools/promote_ledger_seal.py --list          # 承認待ち一覧を表示
    python tools/promote_ledger_seal.py --approve os.popen2
    python tools/promote_ledger_seal.py --reject  os.popen2

[2026-10 訂正] 以前のdocstringには `--approve-all`(全件一括承認)という
オプションが「非推奨だが使用可能」として記載されていたが、実際には
argparseの定義に一度も実装されていなかった(存在しないオプションを
指定するとargparse自体がエラーで終了する)。このツールの存在目的は
「人間が1件ずつ目視確認する」ことそのものであるため、一括承認機能を
後から実装することはせず、実態に合わせてdocstringから記述を削除した。
"""
import argparse
import json
from pathlib import Path

PLEROMA_DIR = Path(__file__).parent.parent
LEDGER_PATH = PLEROMA_DIR / "sefer" / "raziel_ledger.json"
PENDING_LEDGER_PATH = PLEROMA_DIR / "sefer" / "raziel_ledger_pending.json"


def _load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_pending():
    pending = _load_json(PENDING_LEDGER_PATH, [])
    open_items = [p for p in pending if p.get("status") == "PENDING_HUMAN_REVIEW"]
    if not open_items:
        print("承認待ちの提案はありません。")
        return
    for p in open_items:
        print(f"--- {p['event']} (proposed_at={p['proposed_at']}) ---")
        print(f"  攻撃コード抜粋: {p.get('attack_code_excerpt', '')[:200]}")
        print(f"  エラー抜粋    : {p.get('source_error_excerpt', '')[:200]}")
        print()


def _set_status(event_name, new_status):
    pending = _load_json(PENDING_LEDGER_PATH, [])
    found = False
    for p in pending:
        if p["event"] == event_name and p.get("status") == "PENDING_HUMAN_REVIEW":
            p["status"] = new_status
            found = True
    if not found:
        print(f"[エラー] 承認待ちの提案に '{event_name}' は見つかりませんでした。")
        return False
    with open(PENDING_LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=4, ensure_ascii=False)
    return True


def approve(event_name):
    if not _set_status(event_name, "APPROVED"):
        return
    ledger = _load_json(LEDGER_PATH, {"banned_events": []})
    if event_name not in ledger["banned_events"]:
        ledger["banned_events"].append(event_name)
        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=4)
    print(f"[承認] '{event_name}' を raziel_ledger.json に昇格しました。")


def reject(event_name):
    if _set_status(event_name, "REJECTED"):
        print(f"[拒否] '{event_name}' を拒否しました（ledgerには反映されません）。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Raziel's Ledger 承認プロモーションツール")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--approve", metavar="EVENT")
    group.add_argument("--reject", metavar="EVENT")
    args = parser.parse_args()

    if args.list:
        list_pending()
    elif args.approve:
        approve(args.approve)
    elif args.reject:
        reject(args.reject)
