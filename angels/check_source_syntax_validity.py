import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "check_source_syntax_validity - 自動修復監査: sefer/*.py 全てが構文的に妥当(compileできる)ことを検証する。"


# 自動修復監査: sefer/*.py 全てが構文的に妥当(compileできる)ことを検証する。
# 壊れている場合はここで検知し、CIを早期に失敗させる（手動修復を促す）。
import ast

def main():
    broken = []
    for p in (ROOT / "sefer").rglob("*.py"):
        try:
            ast.parse(p.read_text(encoding="utf-8-sig"))  # BOM付きファイルに対応
        except SyntaxError as e:
            broken.append((p.relative_to(ROOT).as_posix(), str(e)))
    if broken:
        report_fail(NAME, f"構文エラーのあるSeferモジュールを検知しました: {broken}")
    report_pass(NAME, "sefer/ 配下の全モジュールが構文的に正常であることを確認しました。")

if __name__ == "__main__":
    main()
