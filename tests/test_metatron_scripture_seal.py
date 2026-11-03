"""
tests/test_metatron_scripture_seal.py
=====================================
[新設 2026-11] angels/metatron_scripture_seal.py の単体テスト。

本天使(「メタトロンの経典印章」)は、「ライセンス証明書機構
(maquina_gatekeeper)・Tartarusの公開配布(pip配布されるseferパッケージ)
からの分離」が将来静かに退行していないかを、`pyproject.toml`・
`MANIFEST.in`・`sefer/*.py`の静的import解析という3点で検証する。

`.github/workflows/anjo_da_maquina_protocol.yml`の§BC由来のコメントが
明記する通り、実際のsdistビルドによる内容検査(`tools/
build_public_scripture.py`・`tests/test_public_scripture_isolation.py`)
は別の仕組みであり、本天使自身の静的検証ロジック(より早期・軽量な層)
を直接検証するテストは、天使群のテストカバレッジの棚卸しの過程で、
一件も存在しないことが判明した。本天使はサプライチェーン境界(配布
境界)を守る中核であるため、優先して対応する。

`main()`は`ROOT / "pyproject.toml"`・`ROOT / "MANIFEST.in"`・
`ROOT / "sefer"`という固定パスを直接読むため、
`metatron_scripture_seal.ROOT`を一時ディレクトリへmonkeypatchし、各
検査項目を満たす/満たさないフィクスチャを置いて検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import metatron_scripture_seal as mss

VALID_PYPROJECT = (
    "[project]\n"
    'name = "sefer"\n'
    "[tool.setuptools]\n"
    'packages = ["sefer"]\n'
)

VALID_MANIFEST = (
    "prune tests\n"
    "exclude maquina_gatekeeper.py\n"
    "exclude ataraxia_certificate.json\n"
)

VALID_SEFER_FILE = (
    "import os\n"
    "import json\n"
    "\n"
    "def hello():\n"
    "    return 'world'\n"
)


def _write_fixtures(root, pyproject=VALID_PYPROJECT, manifest=VALID_MANIFEST,
                     sefer_file_content=VALID_SEFER_FILE, include_pyproject=True,
                     include_manifest=True):
    if include_pyproject:
        (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    if include_manifest:
        (root / "MANIFEST.in").write_text(manifest, encoding="utf-8")
    sefer_dir = root / "sefer"
    sefer_dir.mkdir(parents=True, exist_ok=True)
    (sefer_dir / "__init__.py").write_text(sefer_file_content, encoding="utf-8")


def _expect_fail(monkeypatch, root):
    monkeypatch.setattr(mss, "ROOT", root)
    try:
        mss.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、配布境界が正しく保たれて
    いるため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        mss.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_pyproject_toml_is_missing(monkeypatch, tmp_path):
    """`pyproject.toml`自体が存在しない場合、正しくFAILする。"""
    _write_fixtures(tmp_path, include_pyproject=False)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_manifest_in_is_missing(monkeypatch, tmp_path):
    """`MANIFEST.in`自体が存在しない場合、正しくFAILする。"""
    _write_fixtures(tmp_path, include_manifest=False)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_packages_declaration_is_missing(monkeypatch, tmp_path):
    """`pyproject.toml`に`packages = [...]`の指定自体が無い場合、正しく
    FAILする。"""
    _write_fixtures(tmp_path, pyproject='[project]\nname = "sefer"\n')
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_packages_includes_more_than_sefer(monkeypatch, tmp_path):
    """[核心・配布境界破りの検知] `packages`に`sefer`以外の何か(例:
    `maquina_gatekeeper`・`tartarus`)が混入している場合、正しくFAILする。"""
    bad_pyproject = VALID_PYPROJECT.replace(
        'packages = ["sefer"]', 'packages = ["sefer", "maquina_gatekeeper"]'
    )
    _write_fixtures(tmp_path, pyproject=bad_pyproject)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_manifest_does_not_prune_tests(monkeypatch, tmp_path):
    """`MANIFEST.in`が内部テスト(tests/)を除外していない場合、正しく
    FAILする。"""
    bad_manifest = VALID_MANIFEST.replace("prune tests\n", "")
    _write_fixtures(tmp_path, manifest=bad_manifest)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_manifest_does_not_exclude_gatekeeper_files(monkeypatch, tmp_path):
    """`MANIFEST.in`がライセンス証明書機構関連ファイルを除外していない
    場合、正しくFAILする。"""
    bad_manifest = "prune tests\n"  # maquina_gatekeeper/ataraxia_certificateへの言及が無い
    _write_fixtures(tmp_path, manifest=bad_manifest)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_sefer_file_imports_maquina_gatekeeper_via_import(monkeypatch, tmp_path):
    """[核心・配布境界破りの検知] `sefer/*.py`が`import
    maquina_gatekeeper`の形でライセンス機構をimportしている場合、正しく
    FAILする。"""
    _write_fixtures(tmp_path, sefer_file_content="import maquina_gatekeeper\n")
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_sefer_file_imports_tartarus_via_from_import(monkeypatch, tmp_path):
    """`sefer/*.py`が`from tartarus import ...`の形でTartarusをimport
    している場合も、同様に正しくFAILする。"""
    _write_fixtures(tmp_path, sefer_file_content="from tartarus import armageddon_core\n")
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_sefer_file_has_syntax_error(monkeypatch, tmp_path):
    """`sefer/*.py`がAST解析に失敗する(構文エラーの)場合、正しくFAIL
    する(安全側に倒し、解析不能なファイルを無条件にPASS扱いしない)。"""
    _write_fixtures(tmp_path, sefer_file_content="def broken(:\n    pass\n")
    _expect_fail(monkeypatch, tmp_path)


def test_passes_with_all_valid_fixtures(monkeypatch, tmp_path):
    """全ての条件を満たす最小構成のフィクスチャでは、想定どおりPASS
    する(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    _write_fixtures(tmp_path)
    monkeypatch.setattr(mss, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        mss.main()
    assert "✅ PASS" in buf.getvalue()
