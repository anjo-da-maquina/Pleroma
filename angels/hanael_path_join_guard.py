import sys, os, ast
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, report_not_applicable, ROOT

NAME = "ハナエルの道筋検問 (Hanael's Waypoint - 無検証パス結合の実使用検知)"

# [新設 2026-10 §BT] §11.9フェーズC(「検証した対象」と「実際に使用する
# 対象」が食い違うパターン、いわゆるcheck-vs-use mismatch)の一般化。
#
# 実機で発見した具体例: src/ollama_agent_loop.pyの_execute_safe_action()
# は、以前`target = self.workspace_root / action_req.get("target")`という
# 素朴なパス結合(pathlibの`/`演算子)のみで`target`を構築し、その直後に
# `target.read_text()`/`target.write_text()`で直接使用していた。
# `pathlib.Path.__truediv__`は右辺が絶対パスの場合に左辺を無視して右辺
# そのものを返す仕様があるため、`action_req["target"]`が絶対パスなら
# `target`は実質的に無検証の任意パスになっていた――しかも別のモジュール
# (anjo_interceptor/intent_checker.py)のコメントは「この関数は
# WorkspaceJail.secure_resolve()による封じ込め検証も行う」と主張して
# おり、「検証されていると宣言されているが、実際には検証されていない」
# という、本件の核心である宣言と実態の不一致そのものだった。
#
# [検知方針] 「このパス結合が本当に危険か」を意味論的に完全自動判定する
# ことは不可能なため(他の天使と同じ構造的限界)、具体的な実例の構造を
# そのまま一般化する: 「`/`演算子によるパス結合の代入」の直後、同じ関数
# 内で(介在するsecure_resolve等の検証呼び出しが無いまま)そのパスが
# ファイルI/O(read_text/write_text/open等)に実際に使われている箇所を
# 検知する。
#
# [正直な注記: 本検査の限界] (1) 検証関数の呼び出しを名前の部分一致
# (`secure_resolve`・`_assert_contained_within_workspace`等)で判定して
# おり、同じ役割を持つ独自の検証関数が別名で実装された場合は見逃す
# (誤って危険と判定する偽陽性の方向)。(2) `/`演算子を使わない結合
# (`os.path.join`・f文字列結合等)は検知範囲外。(3) 変数の再代入や
# 別名への代入を経由した場合の追跡は行わない(単純な単一変数の追跡のみ)。

TARGET_DIRS = ["angels", "src", "adapters", "anjo_interceptor"]
TARGET_FILES = ["maquina_gatekeeper.py"]

SANITIZER_NAME_MARKERS = ("secure_resolve", "_assert_contained_within_workspace")
IO_ATTR_NAMES = {"read_text", "write_text", "read_bytes", "write_bytes", "open"}


def _iter_target_files():
    for d in TARGET_DIRS:
        dir_path = ROOT / d
        if not dir_path.exists():
            continue
        for p in sorted(dir_path.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            yield p
    for f in TARGET_FILES:
        p = ROOT / f
        if p.exists():
            yield p


def _direct_children_nodes(func_node):
    """func_node(関数定義)の直接のボディに属する全ての「文」(ast.stmt、
    式も式文としてast.Exprでここに含まれる)を、ネストした別の関数定義
    (def/async def/lambda)の内部には立ち入らずに、出現順(lineno昇順)で
    収集する(barachiel_last_words.pyと同一方針)。ast.stmtのみに限定する
    のは、全ノード(演算子・Load/Store等、lineno属性を持たないものを
    含む)ではなく、文単位の粒度で「ここまでに検証呼び出しがあったか」
    を判定したいため。"""
    nodes = []

    def visit(node, in_nested):
        for child in ast.iter_child_nodes(node):
            child_is_nested_def = isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            )
            if not in_nested and isinstance(child, ast.stmt):
                nodes.append(child)
            visit(child, in_nested or child_is_nested_def)

    visit(func_node, False)
    nodes.sort(key=lambda n: n.lineno)
    return nodes


def _is_sanitizer_call(node) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
    return any(marker in name for marker in SANITIZER_NAME_MARKERS)


def _is_naive_path_join_assign(node):
    """`var = <何か> / <何か>`という形の代入を検出する。戻り値は
    代入先の変数名、またはそうでなければNone。

    [実装中の自己レッドチームで発見・即時修正] 当初は右辺の形を一切
    問わなかったため、`ROOT / "src" / "aegis_system.py"`のような、
    完全に固定されたリテラル文字列のみによる(攻撃者が制御できる要素が
    一切無い)パス結合まで誤検知していた(angels/sandalphon_decree.pyで
    実際に3件の偽陽性を確認)。これは本物のバグ(src/ollama_agent_loop.py
    の`self.workspace_root / action_req.get("target")`、右辺が外部入力
    由来の式)とは本質的に異なる。右辺(結合の最後の要素)が単純な文字列
    リテラルである場合は、外部入力が混入する余地がないとみなし、検知
    対象から除外する。"""
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    if not isinstance(target, ast.Name):
        return None
    if not (isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Div)):
        return None
    if isinstance(node.value.right, ast.Constant):
        return None
    return target.id


def _is_io_use_of_var(node, var_name: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in IO_ATTR_NAMES:
        return isinstance(func.value, ast.Name) and func.value.id == var_name
    if isinstance(func, ast.Name) and func.id == "open":
        return bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == var_name
    return False


def find_unsanitized_path_joins(text: str, filename: str = "<unknown>"):
    """このファイル内で、`/`によるパス結合の代入の後、同じ関数内で
    (間に検証関数呼び出しが無いまま)その変数がファイルI/Oに直接使われて
    いる箇所を検出する。戻り値: [(func_qualname, var_name, join_lineno, use_lineno), ...]"""
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError:
        return []

    findings = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        nodes = _direct_children_nodes(func)

        pending_joins = {}  # var_name -> join_lineno
        for n in nodes:
            var_name = _is_naive_path_join_assign(n)
            if var_name is not None:
                pending_joins[var_name] = n.lineno
                continue
            for sub in ast.walk(n):
                if _is_sanitizer_call(sub):
                    pending_joins.clear()
                    break
            else:
                for var_name, join_lineno in list(pending_joins.items()):
                    for sub in ast.walk(n):
                        if _is_io_use_of_var(sub, var_name):
                            findings.append((func.name, var_name, join_lineno, n.lineno))
                            del pending_joins[var_name]
                            break
    return findings


def main():
    found_any_join = False
    missing = []  # [(file, func, var, join_line, use_line), ...]

    for p in _iter_target_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        try:
            tree = ast.parse(text, filename=str(p))
        except SyntaxError:
            continue
        if not any(
            isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) for n in ast.walk(tree)
        ):
            continue
        found_any_join = True
        for func_name, var_name, join_lineno, use_lineno in find_unsanitized_path_joins(
            text, filename=str(p)
        ):
            missing.append(
                (p.relative_to(ROOT).as_posix(), func_name, var_name, join_lineno, use_lineno)
            )

    if not found_any_join:
        report_not_applicable(NAME, "`/`によるパス結合が存在しないため検査対象なし。")
        return

    if missing:
        detail = "; ".join(
            f"{f}:{func}()の変数{v}(結合: 行{jl}, 使用: 行{ul})" for f, func, v, jl, ul in missing
        )
        report_fail(
            NAME,
            f"検証(secure_resolve等)を経ずに`/`結合されたパスが直接ファイルI/Oに"
            f"使われている箇所が見つかりました(§BTのsrc/ollama_agent_loop.pyと"
            f"同種の、宣言と実態が食い違うフェイルオープン・パターン): {detail}",
            evidence={"missing": missing},
        )
        return

    report_pass(
        NAME,
        "検出した全ての`/`結合パスのファイルI/O利用について、同じ関数内で事前に検証関数が呼ばれていることを確認しました。",
    )


if __name__ == "__main__":
    main()
