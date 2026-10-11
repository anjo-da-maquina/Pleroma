"""
tests/test_adapters_excel_to_yaml_parser.py
=============================================
adapters/excel_to_yaml_parser.py の回帰テスト。GRIMOIRE.md §AJ 参照。

背景: 本ファイルは以前
    import os, sys
    print(f'[Anjo da máquina] Module {__file__} initialized. Zero-Trust audit passed.')
のみで構成される、いかなる処理も行わない「中身のないプレースホルダー」
だった。CIでは「外部要件の抽出 (Excel to YAML Parser)」として常に無条件に
成功を報告していたが、実際にExcelファイルを読んだことは一度もなかった。
本テストは、実際にopenpyxlでExcelを読み込みYAML化する処理が正しく動作
すること、かつ対象ファイルが存在しない場合は正直に「検査対象なし」を
報告すること(偽の成功を報告しないこと)を固定する。
"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "adapters"))

import excel_to_yaml_parser as parser_mod  # noqa: E402


def _reload_with_paths(monkeypatch, source_xlsx: Path, output_yaml: Path):
    monkeypatch.setattr(parser_mod, "SOURCE_XLSX", source_xlsx)
    monkeypatch.setattr(parser_mod, "OUTPUT_YAML", output_yaml)


def test_missing_source_reports_no_target_and_succeeds(tmp_path, monkeypatch):
    """[脆弱性修正の核心] requirements.xlsxが存在しない場合、偽の
    "Zero-Trust audit passed"を名乗ってはならず、正直に検査対象なしを
    報告して正常終了(exit code 0)しなければならない。"""
    source = tmp_path / "requirements.xlsx"
    output = tmp_path / "out" / "external_requirements.yaml"
    _reload_with_paths(monkeypatch, source, output)

    assert parser_mod.main() == 0
    assert not output.exists()


def test_real_excel_file_is_actually_parsed_and_converted_to_yaml(tmp_path, monkeypatch):
    """[脆弱性修正の核心] requirements.xlsxが存在する場合、実際にopenpyxl
    で読み込み、ヘッダ行をキーとするレコードのリストとしてYAML化しなければ
    ならない。"""
    import openpyxl
    import yaml

    source = tmp_path / "requirements.xlsx"
    output = tmp_path / "sefer" / "external_requirements.yaml"
    _reload_with_paths(monkeypatch, source, output)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["requirement_id", "description", "priority"])
    ws.append(["REQ-001", "ログイン機能を実装する", "High"])
    ws.append(["REQ-002", None, "Low"])
    wb.save(str(source))

    assert parser_mod.main() == 0
    assert output.exists()

    with open(output, "r", encoding="utf-8") as f:
        records = yaml.safe_load(f)

    assert records == [
        {"requirement_id": "REQ-001", "description": "ログイン機能を実装する", "priority": "High"},
        {"requirement_id": "REQ-002", "priority": "Low"},
    ]


def test_fully_empty_rows_are_skipped(tmp_path, monkeypatch):
    """完全に空の行(全セルNone)はレコードとして出力されない。"""
    import openpyxl

    source = tmp_path / "requirements.xlsx"
    output = tmp_path / "sefer" / "external_requirements.yaml"
    _reload_with_paths(monkeypatch, source, output)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["a", "b"])
    ws.append([None, None])
    ws.append(["x", "y"])
    wb.save(str(source))

    assert parser_mod.main() == 0
    records = parser_mod.parse_excel_to_rows(source)
    assert records == [{"a": "x", "b": "y"}]
