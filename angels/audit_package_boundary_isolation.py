import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "audit_package_boundary_isolation - 思考統制監査: 「ライセンス証明書機構(maquina_gatekeeper)の公開配布からの 分離」が将来静かに退行していないかを静的に検証する。"


# 思考統制監査: 「ライセンス証明書機構(maquina_gatekeeper)の公開配布からの
# 分離」が将来静かに退行していないかを静的に検証する。
#
# 世界に配る経典(= pip配布されるsefer単体パッケージ)には、ゲートキーパー
# (ライセンス証明書機構)やTartarus(闘技場・Creator's Air)を一切含めない、
# という設計判断を以下の3点で守る:
#   A. pyproject.toml の [tool.setuptools] packages が "sefer" 単体のみ
#      であること(他のディレクトリが紛れ込んでいないか)。
#   B. MANIFEST.in が、運用者向けの内部テスト(tests/)やゲートキーパー
#      関連ファイルを明示的に除外していること。
#   C. sefer パッケージ自身のソース(*.py)が、maquina_gatekeeper や
#      adapters を一切importしていないこと(静的import解析)。
def main():
    pyproject = ROOT / "pyproject.toml"
    manifest = ROOT / "MANIFEST.in"

    if not pyproject.exists():
        report_fail(NAME, "pyproject.toml が見つかりません。")
    if not manifest.exists():
        report_fail(NAME, "MANIFEST.in が見つかりません。公開配布物からtests/等を除外する仕組みが欠落しています。")

    # A: packages = ["sefer"] のみであること
    pyproject_text = pyproject.read_text(encoding="utf-8-sig")
    import re as _re
    m = _re.search(r'packages\s*=\s*\[([^\]]*)\]', pyproject_text)
    if not m:
        report_fail(NAME, "pyproject.tomlに[tool.setuptools] packages の指定が見つかりません。")
    packages_raw = m.group(1)
    packages = [p.strip().strip('"').strip("'") for p in packages_raw.split(",") if p.strip()]
    if packages != ["sefer"]:
        report_fail(NAME, f"配布パッケージが'sefer'単体ではありません(packages={packages})。ゲートキーパー等が混入する恐れがあります。")

    # B: MANIFEST.in が tests/ を明示的に除外していること
    manifest_text = manifest.read_text(encoding="utf-8-sig")
    if "prune tests" not in manifest_text:
        report_fail(NAME, "MANIFEST.inが運用者向け内部テスト(tests/)を除外していません。")
    if "maquina_gatekeeper" not in manifest_text or "ataraxia_certificate" not in manifest_text:
        report_fail(NAME, "MANIFEST.inがライセンス証明書機構関連ファイルを明示的に除外していません。")

    # C: sefer/*.py が maquina_gatekeeper / adapters を一切importしていないこと
    sefer_dir = ROOT / "sefer"
    import ast
    for py_file in sefer_dir.glob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"))
        except Exception as e:
            report_fail(NAME, f"{py_file.name} のAST解析に失敗しました: {e}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("maquina_gatekeeper", "adapters", "tartarus"):
                        report_fail(NAME, f"sefer/{py_file.name} がライセンス機構/Tartarus({alias.name})をimportしています。配布境界が破られています。")
            elif isinstance(node, ast.ImportFrom):
                if node.module in ("maquina_gatekeeper", "adapters", "tartarus"):
                    report_fail(NAME, f"sefer/{py_file.name} がライセンス機構/Tartarus({node.module})をimportしています。配布境界が破られています。")

    report_pass(NAME, "ライセンス証明書機構・Tartarusは、公開配布される経典(seferパッケージ)から正しく分離されています。")

if __name__ == "__main__":
    main()
