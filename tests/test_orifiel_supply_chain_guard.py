"""
tests/test_orifiel_supply_chain_guard.py
=========================================
[新設 2026-10 §BV] angels/orifiel_supply_chain_guard.py の単体テスト。

§11.9フェーズE(未宣言の依存関係・サプライチェーン注入の検知)。
requirements.txtに宣言されていないサードパーティimport、および
CIワークフローがrequirements.txtを経由しない独自のpip installを
行っていないか、の2系統を検査する天使の、自己レッドチームの結果を
固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import orifiel_supply_chain_guard as og


# ---------------------------------------------------------------------------
# A. import走査(_top_level_import_names)のテスト
# ---------------------------------------------------------------------------

def test_simple_import_is_detected():
    import ast
    tree = ast.parse("import numpy as np\n")
    assert og._top_level_import_names(tree) == {"numpy"}


def test_from_import_is_detected():
    import ast
    tree = ast.parse("from foo.bar import baz\n")
    assert og._top_level_import_names(tree) == {"foo"}


def test_comma_separated_import_catches_all_modules():
    """[既知の過去の弱点の修正の固定] regexベースの初期実装案では
    `import a, b, c`のようなカンマ区切りの複数import文で、2番目以降の
    モジュールを見逃す偽陰性があった。ast.parse()ベースの実装への
    切り替えにより、この偽陰性は構造的に解消されている――本テストは
    その回帰を防止する。"""
    import ast
    tree = ast.parse("import os, numpy, sys\n")
    names = og._top_level_import_names(tree)
    assert "numpy" in names
    assert "os" in names and "sys" in names


def test_docstring_text_resembling_an_import_is_not_detected():
    """[既知の過去の弱点の修正の固定] regexベースの初期実装案では、
    docstring内の使用例のテキスト(行頭が`import X`の形)を本物のimport
    文と誤認する偽陽性のリスクがあった。ast.parse()は実際にコードとして
    解析されたimport文のみを見るため、文字列リテラルの内容は対象にならず、
    この偽陽性も構造的に解消されている。"""
    import ast
    tree = ast.parse('"""\n使用例:\nimport numpy as np\n"""\nimport os\n')
    assert og._top_level_import_names(tree) == {"os"}


def test_relative_import_is_excluded():
    """相対import(`from . import x`、level>0)は定義上ローカルモジュール
    であるため、意図的に検査対象から除外する。"""
    import ast
    tree = ast.parse("from . import foo\nfrom .bar import baz\n")
    assert og._top_level_import_names(tree) == set()


def test_submodule_import_resolves_to_top_level_package():
    """`import google.generativeai`のようなサブモジュールimportは、
    トップレベルのパッケージ名(`google`)に正規化される。"""
    import ast
    tree = ast.parse("import google.generativeai as genai\n")
    assert og._top_level_import_names(tree) == {"google"}


# ---------------------------------------------------------------------------
# B. requirements.txt解析・未宣言import検出のテスト
# ---------------------------------------------------------------------------

def test_load_declared_packages_normalizes_names(tmp_path, monkeypatch):
    req = tmp_path / "requirements.txt"
    req.write_text("PyYAML==6.0.3\nrequests>=2.0\n# comment\n\nollama\n")
    monkeypatch.setattr(og, "REQUIREMENTS_PATH", req)
    declared = og.load_declared_packages()
    assert declared == {"pyyaml", "requests", "ollama"}


def test_find_undeclared_imports_flags_missing_package(tmp_path, monkeypatch):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "thing.py").write_text("import undeclared_pkg\n")
    monkeypatch.setattr(og, "ROOT", tmp_path)
    monkeypatch.setattr(og, "TARGET_DIRS_FOR_IMPORT_SCAN", ["src"])
    monkeypatch.setattr(og, "TARGET_FILES_FOR_IMPORT_SCAN", [])
    monkeypatch.setattr(og, "_LOCAL_TOP_LEVEL_DIRS", {"src"})
    undeclared = og.find_undeclared_imports(declared_packages=set())
    assert ("src/thing.py", "undeclared_pkg") in undeclared


def test_find_undeclared_imports_respects_alias_table(tmp_path, monkeypatch):
    """`yaml`は`PyYAML`として宣言されていれば未宣言と判定しない
    (§BVのollama/openai/google-generativeai未宣言バグの再現防止と同種の
    対応表の健全性確認)。"""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "thing.py").write_text("import yaml\n")
    monkeypatch.setattr(og, "ROOT", tmp_path)
    monkeypatch.setattr(og, "TARGET_DIRS_FOR_IMPORT_SCAN", ["src"])
    monkeypatch.setattr(og, "TARGET_FILES_FOR_IMPORT_SCAN", [])
    monkeypatch.setattr(og, "_LOCAL_TOP_LEVEL_DIRS", {"src"})
    undeclared = og.find_undeclared_imports(declared_packages={"pyyaml"})
    assert undeclared == []


def test_find_undeclared_imports_skips_local_sibling_modules(tmp_path, monkeypatch):
    """同一ディレクトリ内の自作モジュール(`src/helper.py`)へのimportは、
    サードパーティ未宣言とは判定しない。"""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "helper.py").write_text("X = 1\n")
    (src_dir / "thing.py").write_text("import helper\n")
    monkeypatch.setattr(og, "ROOT", tmp_path)
    monkeypatch.setattr(og, "TARGET_DIRS_FOR_IMPORT_SCAN", ["src"])
    monkeypatch.setattr(og, "TARGET_FILES_FOR_IMPORT_SCAN", [])
    monkeypatch.setattr(og, "_LOCAL_TOP_LEVEL_DIRS", set())
    undeclared = og.find_undeclared_imports(declared_packages=set())
    assert undeclared == []


def test_find_undeclared_imports_skips_tartarus_local_modules(tmp_path, monkeypatch):
    """
    [脆弱性修正の回帰テスト・核心 §BZ] `tartarus/`配下のローカルモジュール
    (例: `armageddon_core.py`)を、`sys.path.insert()`した上でディレクトリ名
    を介さずトップレベル名でimportする(本リポジトリの`tests/`で既に
    使われている確立済みのパターン)場合、`angels/`配下の新しいファイルが
    同じ流儀でimportしても、サードパーティ未宣言として誤検知しては
    ならない。実機で確認済み: 新設した`angels/sandalphon_rejection_memory_
    guard.py`(§BZ)がこの流儀で`armageddon_core`をimportしたところ、
    修正前の本天使自身がそれを誤検知し、マージ前のリポジトリ全体pytest
    実行で初めて発覚した。
    """
    root = tmp_path
    tartarus_dir = root / "tartarus"
    tartarus_dir.mkdir()
    (tartarus_dir / "armageddon_core.py").write_text("X = 1\n")

    angels_dir = root / "angels"
    angels_dir.mkdir()
    (angels_dir / "some_angel.py").write_text("import armageddon_core\n")

    monkeypatch.setattr(og, "ROOT", root)
    monkeypatch.setattr(og, "TARGET_DIRS_FOR_IMPORT_SCAN", ["angels"])
    monkeypatch.setattr(og, "TARGET_FILES_FOR_IMPORT_SCAN", [])
    monkeypatch.setattr(og, "_LOCAL_TOP_LEVEL_DIRS", set())
    undeclared = og.find_undeclared_imports(declared_packages=set())
    assert undeclared == [], (
        "tartarus/配下のローカルモジュールへのimportが、未宣言のサード"
        "パーティimportとして誤検知されてしまった(§BZの回帰)"
    )


# ---------------------------------------------------------------------------
# C. CIワークフローのpip install乖離検出(_extract_divergent_pip_packages /
#    find_divergent_workflow_installs)のテスト
# ---------------------------------------------------------------------------

def test_extract_divergent_pip_packages_finds_hardcoded_list():
    """[核心・§BVの再現] requirements.txt修正前の実際のバグ行を再現し、
    正しく全パッケージを抽出できることを固定する。"""
    pkgs = og._extract_divergent_pip_packages(
        "pip install networkx pyyaml playwright mcp pandas openpyxl pytest"
    )
    assert pkgs == ["networkx", "pyyaml", "playwright", "mcp", "pandas", "openpyxl", "pytest"]


def test_extract_divergent_pip_packages_ignores_requirements_file_install():
    assert og._extract_divergent_pip_packages("pip install -r requirements.txt") == []


def test_extract_divergent_pip_packages_ignores_pip_upgrade():
    assert og._extract_divergent_pip_packages("python -m pip install --upgrade pip") == []


def test_extract_divergent_pip_packages_handles_pip3():
    """pip3 installという表記も同様に検知する(素のpip installのみを
    見ていた初期実装の弱点に対する、低コストな拡張)。"""
    assert og._extract_divergent_pip_packages("pip3 install foo bar") == ["foo", "bar"]


def test_extract_divergent_pip_packages_on_unrelated_runtime_call_is_a_known_scope_boundary():
    """[正直な注記: 意図的なスコープ境界(偽陽性ではない)]
    `angels/azazel_dependency_audit.py`内部の実行時`subprocess`経由の
    `pip install --quiet pip-audit`相当の文字列は、本関数単体に渡せば
    'pip-audit'を抽出してしまう。しかし、find_divergent_workflow_installs()
    は.github/workflows/*.ymlのrun:ブロックのみを走査し、Pythonソース
    ファイルの文字列は一切見ないため、この関数がPythonソースの文字列に
    対して呼ばれることは実際には無い。本テストは、その境界線を意図的に
    明示するためのものである。"""
    assert og._extract_divergent_pip_packages("pip install --quiet pip-audit") == ["pip-audit"]


def test_find_divergent_workflow_installs_flags_hardcoded_workflow(tmp_path, monkeypatch):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "bad.yml").write_text(
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: install\n"
        "        run: pip install networkx pandas\n"
    )
    monkeypatch.setattr(og, "ROOT", tmp_path)
    monkeypatch.setattr(og, "WORKFLOW_DIR", wf_dir)
    divergent = og.find_divergent_workflow_installs()
    assert len(divergent) == 1
    f, job, step, pkgs = divergent[0]
    assert pkgs == ["networkx", "pandas"]


def test_find_divergent_workflow_installs_does_not_flag_requirements_based_install(tmp_path, monkeypatch):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "good.yml").write_text(
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: install\n"
        "        run: |\n"
        "          python -m pip install --upgrade pip\n"
        "          pip install -r requirements.txt\n"
    )
    monkeypatch.setattr(og, "ROOT", tmp_path)
    monkeypatch.setattr(og, "WORKFLOW_DIR", wf_dir)
    assert og.find_divergent_workflow_installs() == []


def test_find_divergent_workflow_installs_ignores_malformed_yaml(tmp_path, monkeypatch):
    """壊れたYAMLファイルがあっても例外を投げず、単にスキップする。"""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "broken.yml").write_text(": : : not valid yaml : : :\n  -\t- bad\n")
    monkeypatch.setattr(og, "ROOT", tmp_path)
    monkeypatch.setattr(og, "WORKFLOW_DIR", wf_dir)
    assert og.find_divergent_workflow_installs() == []


# ---------------------------------------------------------------------------
# D. main()の統合テスト(NOT_APPLICABLE / 実リポジトリでのPASS)
# ---------------------------------------------------------------------------

def test_no_requirements_txt_reports_not_applicable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(og, "REQUIREMENTS_PATH", tmp_path / "requirements.txt")
    og.main()
    out = capsys.readouterr().out
    assert "⬜ NOT_APPLICABLE" in out


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリの実際のソースコード・
    requirements.txt・CIワークフローに対して本天使を実行し、PASSする
    ことを確認する(§BVで実際に修正した、ollama/openai/
    google-generativeai/setuptoolsの未宣言と、Angelsワークフローの
    ハードコードされたpip installの乖離、両方が解消済みであることの
    回帰防止)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        og.main()
    assert "✅ PASS" in buf.getvalue()
