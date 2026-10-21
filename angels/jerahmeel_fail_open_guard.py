import sys, os, ast
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, report_not_applicable, ROOT

NAME = "イェラミエルの沈黙の番人 (Jerahmeel's Silent Guard - フェイルオープン例外握り潰し検知)"

# [新設 2026-10 §BS] maquina_gatekeeper.pyの_register_audit_hook_once()で
# 実際に発見した本物の脆弱性――本リポジトリ唯一の深層保護
# (sys.addaudithookベースのultimate_audit_hook)の設置処理全体が
# `except Exception: pass`で囲まれていたため、設置自体が失敗しても
# その事実が握り潰され、呼び出し元は「保護は有効である」という偽りの
# 前提のまま処理を継続していた――という「フェイルオープン」パターンを、
# 一般化して機械的に検知する。
#
# [設計方針] 「このexceptは本当に危険か(安全に握り潰してよいものか)」を
# 完全に自動判定することは、意味論的な理解を要するため原理的に不可能
# である(thrones_positive_path.py・barachiel_last_words.pyと同じ構造的
# 限界)。そのため本天使は「危険かどうかの判定」自体はせず、代わりに
# 「本リポジトリが既に自分自身の文化として採用している『正直な自己開示』
# の作法(例: 『[残存する限界(正直に明記する)]』のようなコメント)を、
# 全ての無言の例外握り潰し(`except ...: pass`)に対して義務化する」
# という、開示を強制する仕組みとして実装する。これにより、「安全に握り
# 潰してよい」と判断した場合は、その判断と理由を明示的にコメントとして
# 書くことが要求され、何の説明もなく例外を握り潰すことができなくなる。
#
# [正直な注記: 本検査の限界] (1) except節の本体が厳密に`pass`一文のみ
# の場合のみを「無言の握り潰し」とみなす(`continue`・`...`・条件付きの
# 部分的ログ出力等の亜種は検知範囲外)。(2) 近傍コメントの有無のみを見て
# おり、コメントの内容が本当にその握り潰しを正当化しているかの妥当性
# までは判定しない(コメントさえあれば通過する)。これは「判定」ではなく
# 「開示の強制」が目的であるため、設計上の意図的な限界である。

TARGET_DIRS = ["angels", "src", "adapters"]
TARGET_FILES = ["maquina_gatekeeper.py"]

JUSTIFICATION_MARKERS = (
    "残存する限界", "既知の限界", "正直な注記", "正直に明記", "既知の制限",
)

# tryブロック開始行より、これだけ上の行までを「近傍コメント」の探索範囲とする。
LOOKBACK_LINES = 15


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


def _is_silent_pass_only(body) -> bool:
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def find_undocumented_silent_excepts(text: str, filename: str = "<unknown>"):
    """このファイル内で、本体が`pass`一文のみの無言の例外握り潰しのうち、
    近傍に本リポジトリの『正直な自己開示』マーカーを含むコメントが無い
    ものを検出する。戻り値: [(lineno, handler_type_repr), ...]"""
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError:
        return []

    lines = text.splitlines()
    undocumented = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _is_silent_pass_only(handler.body):
                continue
            handler_repr = (
                ast.unparse(handler.type) if handler.type is not None else "(bare except)"
            )
            window_start = max(0, node.lineno - 1 - LOOKBACK_LINES)
            window_end = min(len(lines), handler.body[-1].end_lineno)
            window_text = "\n".join(lines[window_start:window_end])
            if not any(marker in window_text for marker in JUSTIFICATION_MARKERS):
                undocumented.append((node.lineno, handler_repr))

    return undocumented


def _has_any_except_handler(text: str, filename: str = "<unknown>") -> bool:
    # [実装中の自己発見・即時修正 §BS] 当初`"except" not in text`という
    # 文字列部分一致で判定していたが、thrones_positive_path.pyが自分自身
    # のコメント内の例示コードを誤検知したのと同種のミスにより、
    # 'no except here'のような無関係な文字列リテラル内の"except"という
    # 部分文字列にも反応してしまっていた(自己テストのレッドチームで発見)。
    # astで実際にtry/except構文が存在するかを判定するよう修正する。
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError:
        return False
    return any(isinstance(n, ast.Try) and n.handlers for n in ast.walk(tree))


def main():
    found_any_try = False
    missing = []  # [(file, lineno, handler_repr), ...]

    for p in _iter_target_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not _has_any_except_handler(text, filename=str(p)):
            continue
        found_any_try = True
        for lineno, handler_repr in find_undocumented_silent_excepts(text, filename=str(p)):
            missing.append((p.relative_to(ROOT).as_posix(), lineno, handler_repr))

    if not found_any_try:
        report_not_applicable(NAME, "except節が存在しないため検査対象なし。")
        return

    if missing:
        detail = "; ".join(f"{f}:{ln}({h})" for f, ln, h in missing)
        report_fail(
            NAME,
            f"理由の説明コメントが無い、無言の例外握り潰し(except ...: pass)が"
            f"見つかりました(§BSのmaquina_gatekeeper.py._register_audit_hook_once()"
            f"と同種のフェイルオープン・パターン): {detail}。"
            f"安全に握り潰せると判断した場合は、「残存する限界」「既知の限界」等の"
            f"マーカーを含むコメントで、その判断と理由を明示的に書いてください。",
            evidence={"undocumented": missing},
        )
        return

    report_pass(
        NAME,
        "検出した全ての無言の例外握り潰し(except ...: pass)について、近傍に理由を説明するコメントが存在することを確認しました。",
    )


if __name__ == "__main__":
    main()
