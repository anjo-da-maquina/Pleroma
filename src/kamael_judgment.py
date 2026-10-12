"""
src/kamael_judgment.py
========================
[再構築 2026-10] angelic_shield.py と同じ欠陥を共有していたため作り直した。

  1. 独自実装の `metatrons_seal`(sys.addaudithook)を撤去した。本ファイルは
     対象ファイルを `ast.parse` で静的解析するのみで、コードを一切実行
     しない。実行を伴わない静的解析ツールにOSレベルのaudit hookを仕掛ける
     ことは何の追加保護にもならず、「保護されている」という誤った印象を
     与えるだけの表示だった(angelic_shield.py モジュールdocstring参照)。

  2. `sefer.inquisition()`(Gabriel)で発見・修正したのと同じバグが
     `KamaelInquisitor.visit_Call` にも存在した: `node.func.attr` は
     `os.system(...)` のような呼び出しのバレ属性名(`"system"`)しか
     取得できず、`shield_rules.json` の `blocked_functions` に
     `"os.system"` のような完全修飾名で登録されたルールには一致しなかった。
     Gabrielの修正(GRIMOIRE.md §E)と同じ手法で、呼び出し式から完全修飾
     ドット区切り名を復元し、バレ名・完全修飾名の両方を照合するように
     修正した。既知の限界(別名importでの回避)も同様に残る。

`shield_rules.json` は人間承認済みのルールのみを含む
(`angelic_shield.py` の `ZadkielDominion` が提案し、
`tools/promote_shield_seal.py` で承認されたもの)。
"""
import sys
import json
import ast
from pathlib import Path


def _qualified_call_name(func_node) -> str:
    """
    呼び出し式のASTノードから完全修飾ドット区切り名を復元する。
    例: `os.system(...)` の `node.func` → "os.system"
        `a.b.c(...)` の `node.func` → "a.b.c"
    復元できない場合（単純な名前以外から始まる式など）は空文字を返す。
    [sefer.inquisition() の同種修正(GRIMOIRE.md §E)と同一のロジック]
    """
    parts = []
    node = func_node
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


class KamaelInquisitor(ast.NodeVisitor):
    def __init__(self, rules):
        self.rules = rules
        self.violations = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in self.rules.get("blocked_modules", []):
                self.violations.append(f"異端モジュール '{alias.name}' のインポート (行: {node.lineno})")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module in self.rules.get("blocked_modules", []):
            self.violations.append(f"異端モジュール '{node.module}' からのインポート (行: {node.lineno})")
        for alias in node.names:
            if alias.name in self.rules.get("blocked_functions", []):
                self.violations.append(f"異端関数 '{alias.name}' の直接インポート (行: {node.lineno})")
        self.generic_visit(node)

    def visit_Call(self, node):
        blocked_functions = self.rules.get("blocked_functions", [])
        qualified_name = _qualified_call_name(node.func)

        if isinstance(node.func, ast.Name):
            if node.func.id in blocked_functions:
                self.violations.append(f"異端関数 '{node.func.id}' の実行呼び出し (行: {node.lineno})")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in blocked_functions:
                self.violations.append(f"異端属性/メソッド '{node.func.attr}' の呼び出し (行: {node.lineno})")

        # [2026-10] 完全修飾名(例: "os.system")での照合を追加。
        # バレ名照合と重複する場合は二重報告を避ける。
        if qualified_name and qualified_name in blocked_functions and qualified_name not in (
            node.func.id if isinstance(node.func, ast.Name) else None,
            node.func.attr if isinstance(node.func, ast.Attribute) else None,
        ):
            self.violations.append(f"異端関数 '{qualified_name}' の実行呼び出し (行: {node.lineno})")

        self.generic_visit(node)


def execute_judgment(target_file) -> bool:
    """対象ファイルを審査する。戻り値は「潔白(違反なし)であればTrue」。

    [脆弱性修正 2026-10] 以前の実装は、違反を検知した場合でも
    「実行は不可能です。カマエルが対象を破棄します。」という、実際には
    何も強制していない(sys.exit()もraiseもファイル削除も行わない)
    メッセージを表示するだけだった。CLIとして呼び出した場合の終了コードは
    違反の有無にかかわらず常に0(成功)であり、本スクリプトの呼び出し元が
    終了コードで合否判定しようとすると(例: シェルスクリプトで
    `python src/kamael_judgment.py x.py && python x.py` のように連鎖させる)、
    違反があっても後続処理は常に実行されてしまう構造的な欠陥だった。
    表示文言が主張する「実行不可能」という強制力と、実際の挙動(常に
    正常終了)が一致していない、という本セッションで繰り返し発見している
    「見せかけ」パターンの一種である。

    本修正では、違反検知時・構文異常時にTrue以外(False)を返すようにし、
    `__main__`ブロックでその戻り値に応じて`sys.exit(1)`するようにした。
    呼び出し元が終了コードで実際に合否判定できるようにするための修正で
    あり、ファイルの物理的な削除(「破棄」)まではこの修正の範囲外である
    (削除という破壊的操作を伴う機能が必要であれば、別途明示的な承認
    フローを設けるべきであり、既存の表示文言を達成するためだけに
    安易にファイル削除を追加することはしない)。
    """
    print(f"=== [能天使カマエルの異端審問] '{target_file}' を解剖する ===")
    rules_file = Path("shield_rules.json")
    if not rules_file.exists():
        print("\n[判決: 審査不能] shield_rules.json が見つかりません。")
        return False

    with open(rules_file, "r", encoding="utf-8") as f:
        rules = json.load(f)

    with open(target_file, "r", encoding="utf-8-sig") as f:
        source_code = f.read()

    try:
        tree = ast.parse(source_code)
        inquisitor = KamaelInquisitor(rules)
        inquisitor.visit(tree)

        if inquisitor.violations:
            print("\n[判決: 異端検知] 以下の致命的な防壁ルール違反が見つかりました:")
            for v in inquisitor.violations:
                print(f"  - {v}")
            print("\n=> [結果: 異端確定] このファイルは防壁ルールに違反しています。")
            return False
        else:
            print("\n[判決: 潔白] 違反は見つかりませんでした。")
            return True
    except SyntaxError as e:
        print(f"\n[判決: 構文異常] 解析不能なコード構造です: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    innocent = execute_judgment(sys.argv[1])
    sys.exit(0 if innocent else 1)
