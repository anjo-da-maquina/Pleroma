"""
tests/test_requirements_cover_test_suite_imports.py
========================================================
requirements.txt の回帰テスト。GRIMOIRE.md §AP 参照。

背景: `.github/workflows/sanctuary_ci.yml` は `pip install -r requirements.txt`
のみを依存のインストール手段として使い(別のワークフロー
`anjo_da_maquina_protocol.yml`側のインストール内容は一切反映されない)、
その直後に `pytest tests/ -v -s` を実行する。

本セッション中、`tests/test_adapters_excel_to_yaml_parser.py`(PyYAML・
openpyxlが必要)と`tests/test_sandalphon_anchor_state_persistence.py`
(PyYAMLが必要)を追加した際、requirements.txtへの追記が漏れたまま
マージされていた。この2ファイルは、このサンドボックス環境には元から
PyYAML・openpyxlがプリインストールされていたため、ローカルでは問題なく
PASSし続け、発覚しなかった(実機検証済み: yaml/openpyxl/playwrightの
importを強制的にブロックして再現したところ、計7件のFAIL・1件の新規ERROR
が発生することを確認した)。

本テストは、tests/配下の各ファイルのモジュールレベルのimport文を静的に
解析し、Python標準ライブラリでもリポジトリ内のローカルモジュールでもない
ものが、全てrequirements.txtに(パッケージ名とimport名の既知の差異を
考慮した上で)列挙されていることを固定する。これにより、今後同種の
依存漏れが再発した場合、CIで実際に失敗する前にこのテスト自身が検知する。
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REQUIREMENTS_PATH = ROOT / "requirements.txt"

# パッケージ名(requirements.txtでの表記)と実際のimport名が異なる既知の例外。
PACKAGE_TO_IMPORT_NAME = {
    "pyyaml": "yaml",
}

# requirements.txtの対象外でよい、テストスイート自身が使う軽量な補助ライブラリ
# や、pip管理下に無い(インタプリタ組み込み・C拡張相当の)特殊モジュール。
ALLOWLIST = {"pytest"}  # pytest自身はrequirements.txtに実在するが念のため明示

# tests/配下のテストが `sys.path.insert` 経由でimportするリポジトリ内の
# ローカルモジュール群のディレクトリ。これらの直下にある .py ファイルの
# stem名は「サードパーティ依存」ではないため、照合対象から除外する。
LOCAL_MODULE_DIRS = ["angels", "src", "sefer", "adapters", "anjo_interceptor", "tools", "tartarus"]


def _local_module_names() -> set:
    names = set()
    # リポジトリルート直下の .py ファイル(例: maquina_gatekeeper.py)。
    for p in ROOT.glob("*.py"):
        names.add(p.stem)
    # リポジトリルート直下のパッケージディレクトリ(例: anjo_interceptor/)、
    # および sys.path.insert 経由でモジュール単体としてimportされる
    # サブディレクトリ配下の .py ファイル(例: angels/sandalphon_anchor.py)。
    for d in LOCAL_MODULE_DIRS:
        dir_path = ROOT / d
        if not dir_path.is_dir():
            continue
        names.add(dir_path.name)
        for p in dir_path.glob("*.py"):
            names.add(p.stem)
    return names


def _requirements_import_names() -> set:
    names = set()
    text = REQUIREMENTS_PATH.read_text(encoding="utf-8-sig")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg_name = line.split("==")[0].strip().lower()
        names.add(PACKAGE_TO_IMPORT_NAME.get(pkg_name, pkg_name))
    return names


def _stdlib_names() -> set:
    # Python 3.10+。本リポジトリのワークフローは3.10/3.11を使用する。
    return set(sys.stdlib_module_names) | {"__future__"}


def _top_level_imports_of_file(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    names = set()
    for node in tree.body:  # モジュールレベルのみ(関数内の遅延importは対象外)
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


def test_every_third_party_import_in_test_suite_is_listed_in_requirements_txt():
    """[脆弱性修正の核心] tests/配下のテストファイルがモジュールレベルで
    importするサードパーティパッケージは、全てrequirements.txtに列挙
    されていなければならない。sanctuary_ci.ymlはrequirements.txtのみを
    インストールしてpytestを実行するため、ここに無いパッケージへの依存は
    実際のCIでModuleNotFoundErrorとして失敗する。"""
    stdlib = _stdlib_names()
    local = _local_module_names()
    required = _requirements_import_names()

    violations = {}
    for test_file in sorted((ROOT / "tests").glob("test_*.py")):
        imports = _top_level_imports_of_file(test_file)
        unresolved = imports - stdlib - local - required - ALLOWLIST
        if unresolved:
            violations[test_file.name] = sorted(unresolved)

    assert not violations, (
        "以下のテストファイルが、requirements.txtに列挙されていない"
        f"サードパーティ依存をモジュールレベルでimportしています: {violations}\n"
        "sanctuary_ci.ymlの実際のCI環境ではこれらのパッケージは存在せず、"
        "ModuleNotFoundErrorで失敗します。requirements.txtに追記してください。"
    )


def test_playwright_and_pyyaml_and_openpyxl_are_now_pinned_in_requirements():
    """[回帰防止] 本セッションで実際に漏れていた3パッケージが、
    requirements.txtに確実に存在することを明示的に固定する。"""
    required = _requirements_import_names()
    for pkg in ("yaml", "openpyxl", "playwright"):
        assert pkg in required, f"'{pkg}' がrequirements.txtから欠落しています。"
