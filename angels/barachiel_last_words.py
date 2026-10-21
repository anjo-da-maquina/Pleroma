import sys, os, ast
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, report_not_applicable, ROOT

NAME = "バラキエルの遺言 (Barachiel's Last Words - 自壊直前ログflush漏れ検知)"

# [新設 2026-10 §BR] §BQで、src/deadmans_switch.pyのCollarProtocol
# ._commit_suicide()とsrc/starvation_protocol.pyのStarvationProtocol
# ._starve()の2箇所に、実機CIでのみ発火する本物の欠陥を発見した――
# os._exit()はPythonの正常な終了処理(標準出力バッファのflush)を一切
# 行わないため、自壊直前にprint()した「なぜ自壊したか」という最も重要な
# 記録が、標準出力がパイプ/ファイルの場合に消失してしまう、という欠陥
# である。
#
# 本天使は、この具体的な2件を直接検査するのではなく(それは既存の個別
# テストの役割)、同じ構造を持つ"まだ見つかっていない"新しい箇所が今後
# 追加された際に、マージ前に機械的に検知するための一般化された検査で
# ある(GRIMOIRE.md §BQ「残存する限界」・§11.9運用ルール参照)。
#
# [正直な注記: 本検査の限界] astによる静的解析のため、thrones_positive_
# path.pyの正規表現ヒューリスティックよりは堅牢だが、それでも以下は
# 検知できない: (1) os._exit()を呼ぶ前に、flush漏れを起こす別の関数を
# 間接的に呼び出す形(例: `self._commit_suicide_impl()`のように自壊処理
# 自体を別関数に切り出し、そちらでflushしている場合、本天使は呼び出し元
# の関数しか見ないため誤検知する可能性は無いが、逆に複雑な別関数委譲の
# 連鎖までは追跡しない)、(2) flush()は呼ばれているが、os._exit()より後
# の無意味な位置にある場合(行番号の前後関係のみで判定しており、実際の
# 制御フロー(if/elseの分岐違いなど)までは解析しない)、(3) `os`が別名
# でimportされている場合(`import os as _os`等)。

TARGET_DIRS = ["angels", "src", "adapters"]
TARGET_FILES = ["maquina_gatekeeper.py"]


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


def _is_os_exit_call(node) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_exit"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
    )


def _is_flush_call(node) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "flush"
    )


def _direct_children_calls(func_node):
    """func_node(関数定義)の直接のボディに属する全Call式を、ネストした
    別の関数定義(def/async def/lambda)の内部には立ち入らずに、出現順
    (lineno昇順)で収集する。"""
    calls = []

    def visit(node, in_nested):
        for child in ast.iter_child_nodes(node):
            child_is_nested_def = isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            )
            if isinstance(child, ast.Call) and not in_nested:
                calls.append(child)
            visit(child, in_nested or child_is_nested_def)

    visit(func_node, False)
    calls.sort(key=lambda n: n.lineno)
    return calls


def find_unflushed_exits(text: str, filename: str = "<unknown>"):
    """このファイル内で、同じ関数のボディの中で、os._exit()呼び出しより
    前にflush()呼び出しが一度も現れないケースを検出する。
    戻り値: [(func_qualname, lineno), ...]"""
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError:
        return []

    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = _direct_children_calls(node)
        flushed_so_far = False
        for call in calls:
            if _is_flush_call(call):
                flushed_so_far = True
            elif _is_os_exit_call(call) and not flushed_so_far:
                missing.append((node.name, call.lineno))
    return missing


def main():
    found_any_exit = False
    missing = []  # [(file, func, lineno), ...]

    for p in _iter_target_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "os._exit(" not in text:
            continue
        found_any_exit = True
        for func_name, lineno in find_unflushed_exits(text, filename=str(p)):
            missing.append((p.relative_to(ROOT).as_posix(), func_name, lineno))

    if not found_any_exit:
        report_not_applicable(NAME, "os._exit()の呼び出しが存在しないため検査対象なし。")
        return

    if missing:
        detail = "; ".join(f"{f}:{func}()(行{ln})" for f, func, ln in missing)
        report_fail(
            NAME,
            f"os._exit()の直前にflush()呼び出しが無い関数が見つかりました"
            f"(§BQのdeadmans_switch.py/starvation_protocol.pyと同種のパターン、"
            f"自壊理由がログに残らない恐れがあります): {detail}",
            evidence={"missing": missing},
        )
        return

    report_pass(
        NAME,
        "検出した全てのos._exit()呼び出しについて、同じ関数内で事前にflush()が呼ばれていることを確認しました。",
    )


if __name__ == "__main__":
    main()
