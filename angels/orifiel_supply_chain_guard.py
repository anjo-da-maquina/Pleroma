import sys, os, re, ast, shlex
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml
from _common import report_pass, report_fail, report_not_applicable, ROOT

NAME = "オリフィエルの検問 (Orifiel's Checkpoint - 未宣言依存関係・サプライチェーン注入検知)"

# [新設 2026-10 §BV] §11.9フェーズE(未宣言の依存関係・サプライチェーン
# 注入の検知)。requirements.txtは、本リポジトリが「依存関係の単一の正」
# として既に(.github/workflows/sanctuary_ci.yml自身のコメント§APで)
# 明記している方針である。しかし実際に調査したところ、以下2種類の
# 「宣言と実態の食い違い」を発見した:
#
#   A. src/ollama_agent_loop.py等、5ファイルが`import ollama`を無条件に
#      行っていたが、requirements.txtにはollamaが一度も宣言されて
#      いなかった(src/openai_agent_loop.py・src/secure_oracle_feed.pyの
#      `openai`・`google.generativeai`は例外処理で保護されていたが、
#      これらも同様に未宣言だった)。
#   B. .github/workflows/anjo_da_maquina_protocol.ymlの依存インストール
#      ステップが、requirements.txtとは無関係に`pip install networkx
#      pyyaml playwright mcp pandas openpyxl pytest`を直接ハードコード
#      していた。このうちnetworkx・mcp・pandasはリポジトリ全体を検索
#      しても一箇所もimportされておらず、完全に不要かつバージョン無
#      指定(サプライチェーン上の無用な攻撃面)のままインストールされて
#      いた。
#
# 本天使は、この2種類のパターンをそれぞれ一般化して継続的に検査する。
#
# [正直な注記: 本検査の限界] (1) importの走査はast(抽象構文木)に基づく
# 静的解析であり、`importlib.import_module(動的な文字列)`のような
# 動的importは検知できない。当初はregex(正規表現)での行単位の走査を
# 検討したが、自己レッドチームの結果、regexには「`import a, b`のような
# カンマ区切りの複数import文で2番目以降のモジュールを見逃す」「docstring
# 内の説明用コード例の行(例: `'''使用例:\nimport numpy as np\n'''`)を
# 本物のimportと誤認する」という2つの偽陰性・偽陽性のリスクが見つかった
# ため、regexではなくast.parse()ベースの実装に切り替えた――これにより
# 両方の問題が構造的に解消される(astは実際に解析されたコード上のimport
# 文のみを見るため、文字列リテラルの内容やカンマ区切りの全モジュールを
# 正しく扱える)。(2) 相対import(`from . import x`等、level>0)は、
# 定義上リポジトリ内部のローカルモジュールであるため、意図的に検査対象
# から除外している。(3) パッケージ名とimport名が異なる場合(例:
# PyYAML→yaml、google-generativeai→google.generativeai)は、既知の
# 対応表(_IMPORT_TO_PACKAGE_ALIASES)で変換するが、この表に載っていない
# 未知のパッケージについては誤って「未宣言」と判定する可能性がある
# (偽陽性の方向)。(4) ワークフローのrun:ステップ内の`pip install`のみを
# 検査しており、Pythonスクリプト内部からの`subprocess`経由の動的な
# `pip install`(例: angels/azazel_dependency_audit.pyが実行時に
# pip-auditを自己インストールする箇所)は検査対象外――これは静的な
# requirements.txt宣言と対比すべき「宣言された依存」ではなく、実行時
# にのみ発生する別種のサプライチェーン上の関心事であり、本天使の
# スコープを超えるため、意図的に将来の課題として切り出す。

TARGET_DIRS_FOR_IMPORT_SCAN = [
    "angels", "src", "adapters", "anjo_interceptor", "sefer", "tools",
]
TARGET_FILES_FOR_IMPORT_SCAN = ["maquina_gatekeeper.py"]

REQUIREMENTS_PATH = ROOT / "requirements.txt"
WORKFLOW_DIR = ROOT / ".github" / "workflows"

# import名(小文字・ハイフン→アンダースコア正規化後)→ requirements.txt
# 上のパッケージ名、への既知の対応表。
_IMPORT_TO_PACKAGE_ALIASES = {
    "yaml": "pyyaml",
    "google": "google-generativeai",
}

_STDLIB_NAMES = set(getattr(sys, "stdlib_module_names", ()))
# このリポジトリ自身が持つトップレベルのディレクトリ名も、ローカルの
# importとして除外する(例: `import adapters`・`import sefer`)。
_LOCAL_TOP_LEVEL_DIRS = {
    p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")
}

def _iter_scanned_files():
    for d in TARGET_DIRS_FOR_IMPORT_SCAN:
        dir_path = ROOT / d
        if not dir_path.exists():
            continue
        for p in sorted(dir_path.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            yield p
    for f in TARGET_FILES_FOR_IMPORT_SCAN:
        p = ROOT / f
        if p.exists():
            yield p


def _is_local_module_name(name: str) -> bool:
    if name in _LOCAL_TOP_LEVEL_DIRS:
        return True
    # リポジトリ直下、またはスキャン対象ディレクトリ直下に
    # <name>.pyが存在する場合もローカルモジュールとみなす。
    for d in [ROOT, *[ROOT / td for td in TARGET_DIRS_FOR_IMPORT_SCAN]]:
        if (d / f"{name}.py").exists():
            return True
    return False


def _normalize_package_name(name: str) -> str:
    return name.lower().replace("_", "-")


def load_declared_packages() -> set:
    if not REQUIREMENTS_PATH.exists():
        return set()
    declared = set()
    for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = re.split(r"[=<>!~\[]", line, maxsplit=1)[0].strip()
        if pkg:
            declared.add(_normalize_package_name(pkg))
    return declared


def _top_level_import_names(tree: ast.AST):
    """astツリーから、importされている全モジュールのトップレベル名
    (`import google.generativeai`→`google`等)の集合を返す。相対import
    (level>0、例: `from . import x`)は定義上ローカルモジュールのため
    除外する。"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if getattr(node, "level", 0):
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def find_undeclared_imports(declared_packages: set):
    """スキャン対象ファイル群から、requirements.txtに宣言されていない
    サードパーティのimportを検出する。戻り値: [(file, import_name), ...]"""
    undeclared = []
    for p in _iter_scanned_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(text, filename=str(p))
        except (SyntaxError, ValueError):
            continue
        for name in sorted(_top_level_import_names(tree)):
            if name in _STDLIB_NAMES or _is_local_module_name(name):
                continue
            pkg = _IMPORT_TO_PACKAGE_ALIASES.get(name, name)
            normalized = _normalize_package_name(pkg)
            if normalized in declared_packages:
                continue
            undeclared.append((p.relative_to(ROOT).as_posix(), name))
    return undeclared


def _extract_divergent_pip_packages(line: str):
    """`pip install`を含む1行から、requirements.txt経由ではない、直接
    指定されたパッケージ名のトークンを抽出する。"""
    marker = "pip install" if "pip install" in line else ("pip3 install" if "pip3 install" in line else None)
    if marker is None:
        return []
    after = line.split(marker, 1)[1]
    try:
        tokens = shlex.split(after)
    except ValueError:
        tokens = after.split()
    packages = []
    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if tok in ("-r", "--requirement"):
            skip_next = True
            continue
        if tok.startswith("-"):
            continue
        if tok == "pip":
            continue
        packages.append(tok)
    return packages


def find_divergent_workflow_installs():
    """全ワークフローファイルのrun:ステップから、requirements.txtを経由
    しない直接指定のpip installパッケージを検出する。
    戻り値: [(workflow_file, job, step, packages), ...]"""
    if not WORKFLOW_DIR.exists():
        return []
    divergent = []
    for wf_path in sorted(WORKFLOW_DIR.glob("*.yml")):
        try:
            workflow = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(workflow, dict):
            continue
        for job_name, job in (workflow.get("jobs") or {}).items():
            for step in job.get("steps", []):
                run_cmd = str(step.get("run", ""))
                for line in run_cmd.splitlines():
                    packages = _extract_divergent_pip_packages(line)
                    if packages:
                        divergent.append(
                            (
                                wf_path.relative_to(ROOT).as_posix(),
                                job_name,
                                step.get("name", "(名前無し)"),
                                packages,
                            )
                        )
    return divergent


def main():
    if not REQUIREMENTS_PATH.exists():
        report_not_applicable(NAME, "requirements.txt が存在しないため検査対象なし。")
        return

    declared = load_declared_packages()
    undeclared_imports = find_undeclared_imports(declared)
    divergent_installs = find_divergent_workflow_installs()

    problems = []
    if undeclared_imports:
        detail = "; ".join(f"{f}(import {n})" for f, n in undeclared_imports)
        problems.append(
            f"requirements.txtに未宣言のサードパーティimportが見つかりました: {detail}"
        )
    if divergent_installs:
        detail = "; ".join(f"{f}:{j}:{s}({', '.join(pkgs)})" for f, j, s, pkgs in divergent_installs)
        problems.append(
            f"requirements.txtを経由しない、pip installの直接指定がCIワークフローに"
            f"見つかりました(§BVのangels/*.py用ワークフローと同種の依存関係の乖離): {detail}"
        )

    if problems:
        report_fail(
            NAME,
            " / ".join(problems),
            evidence={
                "undeclared_imports": undeclared_imports,
                "divergent_installs": divergent_installs,
            },
        )
        return

    report_pass(
        NAME,
        "検出した全てのサードパーティimportがrequirements.txtに宣言されており、"
        "CIワークフローのpip installもrequirements.txt経由に統一されていることを確認しました。",
    )


if __name__ == "__main__":
    main()
