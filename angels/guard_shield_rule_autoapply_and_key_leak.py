import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "guard_shield_rule_autoapply_and_key_leak (Warden) - 思考統制監査: src/angelic_shield.py / src/kamael_judgment.py の再構築が…"

# 思考統制監査: src/angelic_shield.py / src/kamael_judgment.py の再構築が、
# 以下3点の修正を保ったままであることを静的に検証する。
#   A. ZadkielDominionがLLM生出力をshield_rules.jsonへ直接反映せず、
#      人間承認待ちキュー(shield_rules_pending.json)に積むのみであること
#      (tartarus/armageddon.py の raziel_ledger_pending.json と同一原則)。
#   B. tools/promote_shield_seal.py による人間承認の昇格経路が存在すること。
#   C. GEMINI_API_KEY を os.environ.pop() で即時消去していること
#      (os.environ.get() のままの読み取り専用アクセスに戻っていないか)。
#   D. KamaelInquisitorが完全修飾名(例: "os.system")でも照合すること
#      (sefer.inquisition()と同一の修正、GRIMOIRE.md §E/§I参照)。


def main():
    shield_path = ROOT / "src" / "angelic_shield.py"
    judgment_path = ROOT / "src" / "kamael_judgment.py"
    promote_tool_path = ROOT / "tools" / "promote_shield_seal.py"

    for p in (shield_path, judgment_path, promote_tool_path):
        if not p.exists():
            report_fail(NAME, f"必須ファイルが見つかりません: {p}")
            return

    shield_text = shield_path.read_text(encoding="utf-8-sig")
    judgment_text = judgment_path.read_text(encoding="utf-8-sig")

    # A: 人間承認待ちキューへの提案のみ（直接反映の禁止）
    if "shield_rules_pending" not in shield_text:
        report_fail(NAME, "ZadkielDominionが承認待ちキュー(shield_rules_pending.json)を使用していません。")
    if "def assimilate_knowledge" in shield_text:
        report_fail(NAME, "LLM出力を即時反映する旧メソッド 'assimilate_knowledge' が復活しています。"
                           "'propose_knowledge' によるキューイングのみを許可します。")

    # B: 人間承認ツールの存在
    promote_text = promote_tool_path.read_text(encoding="utf-8-sig")
    if "PENDING_HUMAN_REVIEW" not in promote_text:
        report_fail(NAME, "promote_shield_seal.pyに人間承認待ちステータスの処理が見つかりません。")

    # C: APIキーの即時消去
    if "os.environ.pop(\"GEMINI_API_KEY\"" not in shield_text and "os.environ.pop('GEMINI_API_KEY'" not in shield_text:
        report_fail(NAME, "GEMINI_API_KEYがos.environ.pop()で即時消去されていません(窃取防止の欠落)。")

    # D: KamaelInquisitorの完全修飾名照合
    if "_qualified_call_name" not in judgment_text:
        report_fail(NAME, "KamaelInquisitorが完全修飾関数名(例: 'os.system')を照合していません。"
                           "sefer.inquisition()と同じドット付き禁止名の検知漏れが再発しています。")

    # E: 誤解を招く独自audit hookの重複実装が復活していないか
    if "def metatrons_seal" in shield_text or "def metatrons_seal" in judgment_text:
        report_fail(NAME, "撤去済みの独自audit hook実装(metatrons_seal)が復活しています。"
                           "実行を伴わない本ファイル群にOSレベルhookを装う表示は誤解を招くため禁止します。")

    report_pass(NAME, "外部脅威インテリジェンス取り込み(angelic_shield.py/kamael_judgment.py)が、"
                       "人間承認ゲート・APIキー即時消去・完全修飾名照合を保ったまま提供されています。")


if __name__ == "__main__":
    main()
