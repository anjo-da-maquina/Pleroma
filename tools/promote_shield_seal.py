"""
Shield Rules 承認プロモーションツール
========================================
[新設 2026-10] `src/angelic_shield.py` の `ZadkielDominion` が
Gemini(LLM)から取得した脅威情報を元に提案した防壁ルール
(`sefer/shield_rules_pending.json`)を、人間が内容を確認した上で
`shield_rules.json`(実際に `src/kamael_judgment.py` が使用する
有効な禁止ルール)へ昇格させるためのツール。

これにより、未検証のLLM出力（プロンプトインジェクション・幻覚を含む）が
そのまま実運用の防御ルールに反映されることを防ぐ。
`tools/promote_ledger_seal.py`(Armageddon Engine向け)と同一のパターン。

使い方:
    python tools/promote_shield_seal.py --list
    python tools/promote_shield_seal.py --approve "<vulnerability_name>"
    python tools/promote_shield_seal.py --reject  "<vulnerability_name>"
"""
import argparse
import json
from pathlib import Path

PLEROMA_DIR = Path(__file__).parent.parent
RULES_PATH = PLEROMA_DIR / "shield_rules.json"
PENDING_RULES_PATH = PLEROMA_DIR / "sefer" / "shield_rules_pending.json"


def _load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_pending():
    pending = _load_json(PENDING_RULES_PATH, [])
    open_items = [p for p in pending if p.get("status") == "PENDING_HUMAN_REVIEW"]
    if not open_items:
        print("承認待ちの提案はありません。")
        return
    for p in open_items:
        print(f"--- {p['vulnerability_name']} (proposed_at={p['proposed_at']}) ---")
        print(f"  説明          : {p.get('description', '')[:200]}")
        print(f"  禁止モジュール案: {p.get('dangerous_modules', [])}")
        print(f"  禁止関数案    : {p.get('dangerous_functions', [])}")
        print()


def _set_status(vuln_name, new_status):
    """承認待ち(PENDING_HUMAN_REVIEW)のエントリのうち、`vuln_name`に一致する
    ものだけを`new_status`に更新する。

    [脆弱性修正 2026-10 §AT] 戻り値を`pending`(全件)だけでなく、
    実際に今回ステータスを変更した(=まさに人間が`--list`で見て承認/拒否
    した)エントリそのもののリストも返すようにした。詳細はGRIMOIRE.md §AT
    参照(同じ`vulnerability_name`で2度目の提案が承認された際、古い
    (既に承認済みの)提案のデータが誤って再適用されてしまう欠陥があった)。
    """
    pending = _load_json(PENDING_RULES_PATH, [])
    changed = [
        p for p in pending
        if p["vulnerability_name"] == vuln_name and p.get("status") == "PENDING_HUMAN_REVIEW"
    ]
    if not changed:
        print(f"[エラー] 承認待ちの提案に '{vuln_name}' は見つかりませんでした。")
        return None, []
    for p in changed:
        p["status"] = new_status
    with open(PENDING_RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)
    return pending, changed


def approve(vuln_name):
    """
    [脆弱性修正 2026-10 §AT] 以前の実装は、ステータス更新後に
    `next(p for p in pending if p["vulnerability_name"] == vuln_name and
    p["status"] == "APPROVED")`で「名前が一致しステータスがAPPROVED」の
    エントリを再検索していた。しかし同じ`vulnerability_name`で過去に
    別の提案が既に承認済み(ステータス"APPROVED")として残っている場合、
    `next()`はリストの先頭から見つかった最初の一致、つまり**古い**承認済み
    エントリを返してしまい、たった今`--list`で人間が確認して承認した
    **新しい**提案の`dangerous_modules`/`dangerous_functions`ではなく、
    古い提案のデータがshield_rules.jsonに適用されてしまう構造的な欠陥が
    あった(実機検証済み: 同一vulnerability_nameで2回提案・承認を行うと、
    2回目に承認したはずの内容が無視され、1回目の内容が再適用されることを
    確認)。`tools/promote_provisioning_seal.py`は同種の重複ケースを
    `matches[-1]`(最新のものを採用)で正しく処理していたのに対し、本ファイル
    だけこの対策が欠けていた、という非対称な状態だった。

    本修正では、`_set_status()`が「今回まさにPENDING_HUMAN_REVIEWから
    new_statusへ遷移させたエントリ」だけを明示的に返すようにし、それら
    (複数ある場合は全件の和集合)だけをshield_rules.jsonへ適用する。古い
    承認済みエントリを誤って再適用することはなくなった。
    """
    pending, changed = _set_status(vuln_name, "APPROVED")
    if pending is None:
        return

    rules = _load_json(RULES_PATH, {"blocked_modules": [], "blocked_functions": []})
    new_modules = set()
    new_functions = set()
    for proposal in changed:
        new_modules |= set(proposal.get("dangerous_modules", []))
        new_functions |= set(proposal.get("dangerous_functions", []))
    rules["blocked_modules"] = sorted(set(rules.get("blocked_modules", [])) | new_modules)
    rules["blocked_functions"] = sorted(set(rules.get("blocked_functions", [])) | new_functions)
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    print(f"[承認] '{vuln_name}' を shield_rules.json に昇格しました。")


def reject(vuln_name):
    pending, _changed = _set_status(vuln_name, "REJECTED")
    if pending is not None:
        print(f"[拒否] '{vuln_name}' を拒否しました（shield_rules.jsonには反映されません）。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shield Rules 承認プロモーションツール")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--approve", metavar="VULNERABILITY_NAME")
    group.add_argument("--reject", metavar="VULNERABILITY_NAME")
    args = parser.parse_args()

    if args.list:
        list_pending()
    elif args.approve:
        approve(args.approve)
    elif args.reject:
        reject(args.reject)
