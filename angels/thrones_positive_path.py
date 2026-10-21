import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, report_info, report_not_applicable, ROOT

NAME = "座天使の陣性経路 (Thrones Positive-Path)"

# [新設 2026-10 §BP] §BM(CHAOS_MODE)・§BN(HMAC連鎖)・§BP(shamir_seal.py)の
# 3件は、いずれも共通のパターンだった: 環境変数/フラグによって有効・無効が
# 切り替わるセキュリティ上重要な分岐が存在するのに、「有効側(危険側)の
# 分岐が実際に発火した場合にどうなるか」を検証するテストが、どのテスト
# ファイルにも一件も存在していなかった。
#
# 本天使は、この具体的な3件を直接検査するのではなく(それは既存の個別
# テストの役割)、同じ構造を持つ"まだ見つかっていない"新しい箇所が
# angels/*.py・src/*.py・adapters/*.py・maquina_gatekeeper.pyに今後
# 追加された際に、マージ前に機械的に検知するための一般化された検査である
# (GRIMOIRE.md §BP「残存する限界」・§11.9運用ルール参照)。
#
# [正直な注記: 本検査の限界] これは厳密な静的解析ではなく、正規表現による
# ヒューリスティックである。(1) 変数経由ではない直接比較
# (`if os.getenv(環境変数名) == "true":`のような形)、(2) 変数経由
# (`y = os.getenv(環境変数名); if y:`のような形)の2形を検知するが、意味的に同値な別の書き方
# (`os.environ["X"]`を関数に包んで呼ぶ、`ctypes`経由等)は検知できない。
# また「テストファイルが環境変数名を含み、assertも含む」ことだけを以って
# 「有効側の分岐を実際に踏んでいる」と推定しており、本当にその分岐を
# 踏んでいるかの保証ではない(§11.9フェーズFの「同値表現による回避」が
# この限界の一般形)。

TARGET_DIRS = ["angels", "src", "adapters"]
TARGET_FILES = ["maquina_gatekeeper.py"]

# ログ出力のみ等、制御フローに影響しないことが分かっている変数名は除外する。
KNOWN_NON_GATING_VARS = {"GITHUB_RUN_ID", "GITHUB_WORKFLOW"}

_ASSIGN_RE = re.compile(
    r'(\w+)\s*=\s*os\.(?:getenv|environ\.get)\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'
    r'|(\w+)\s*=\s*os\.environ\[\s*["\']([A-Z_][A-Z0-9_]*)["\']\s*\]'
)
_DIRECT_IF_RE = re.compile(
    r'if\s+(?:not\s+)?os\.(?:getenv|environ\.get)\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'
    r'|if\s+(?:not\s+)?os\.environ\[\s*["\']([A-Z_][A-Z0-9_]*)["\']\s*\]'
)


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


def _strip_full_line_comments(text: str) -> str:
    """[実装中のレッドチーム自己発見・ブルーチーム即時対応] 本検査を
    angels/thrones_positive_path.py自身に対して実行したところ、本ファイル
    自身のコメント内に書いた説明用の例示コード
    (説明文中に例示コードを書くと、その例示コード自体を検査対象として誤認識する)を、本物の環境変数ゲートと
    誤検知した(環境変数名"X"が誤って抽出された)。説明目的の例示コードを
    含むコメントが、正規表現ベースの検査対象に混入するのは本質的に
    避けられないため、一行全体がコメント(`#`で始まる行)である行は、
    スキャン対象のテキストから事前に取り除くことで、個別対応ではなく
    一般的に再発を防ぐ。"""
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )


def find_env_gated_vars(text: str):
    """このファイル内で、環境変数が条件分岐のゲートとして使われている
    (ログ出力等ではなく、制御フローに影響する)ものを抽出する。
    戻り値: [(env_var_name, is_gating), ...]"""
    text = _strip_full_line_comments(text)
    found = {}

    for m in _DIRECT_IF_RE.finditer(text):
        env_var = m.group(1) or m.group(2)
        found[env_var] = True

    for m in _ASSIGN_RE.finditer(text):
        if m.group(1) is not None:
            py_var, env_var = m.group(1), m.group(2)
        else:
            py_var, env_var = m.group(3), m.group(4)
        # この python変数名が、後続のif文のゲートとして実際に使われているか。
        if_pat = re.compile(r'if\s+(?:not\s+)?' + re.escape(py_var) + r'\b')
        if if_pat.search(text):
            found[env_var] = True

    return {k: v for k, v in found.items() if k not in KNOWN_NON_GATING_VARS}


def _load_all_test_text():
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return ""
    chunks = []
    for p in sorted(tests_dir.rglob("*.py")):
        try:
            chunks.append(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
    return "\n".join(chunks)


def main():
    all_test_text = _load_all_test_text()
    if not all_test_text:
        report_not_applicable(NAME, "tests/ が存在しないため検査対象なし。")
        return

    missing = []  # [(file, env_var), ...]
    checked_vars = set()

    for p in _iter_target_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        gated_vars = find_env_gated_vars(text)
        for env_var in gated_vars:
            checked_vars.add(env_var)
            # テストファイル全体の中に、この環境変数名への言及と、何らかの
            # assertが(同じファイル内に)存在するか。
            has_coverage = False
            tests_dir = ROOT / "tests"
            for tp in sorted(tests_dir.rglob("*.py")) if tests_dir.exists() else []:
                try:
                    ttext = tp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if env_var in ttext and "assert" in ttext:
                    has_coverage = True
                    break
            if not has_coverage:
                missing.append((p.relative_to(ROOT).as_posix(), env_var))

    if missing:
        detail = "; ".join(f"{f} (環境変数 {v})" for f, v in missing)
        report_fail(
            NAME,
            f"環境変数で有効/無効が切り替わるセキュリティ上重要な分岐に、"
            f"有効側の分岐を実際に踏むテストが見つかりません(§BM/§BN/§BPと同種のパターン): {detail}",
            evidence={"missing": missing, "checked_env_vars": sorted(checked_vars)},
        )
        return

    report_pass(
        NAME,
        f"{len(checked_vars)}件の環境変数ゲート付き分岐すべてに、対応するテストファイルでの言及を確認しました。",
        evidence={"checked_env_vars": sorted(checked_vars)},
    )


if __name__ == "__main__":
    main()
