"""
adapters/excel_to_yaml_parser.py
===================================
[脆弱性修正 2026-10 §AJ] 以前の実装は、以下の2行のみで構成される、
いかなる処理も行わない「中身のないプレースホルダー」だった:

    import os, sys
    print(f'[Anjo da máquina] Module {__file__} initialized. Zero-Trust audit passed.')

CIワークフロー(.github/workflows/anjo_da_maquina_protocol.yml)では、本
ステップは「3.8. 外部要件の抽出 (Excel to YAML Parser)」として実行され、
常に例外なく成功する(exit code 0)ため、あたかも実際に外部のExcelファイル
から要件を抽出しYAML化する処理が行われ合格したかのように報告していたが、
実際には何も処理していなかった。これは`angels/*.py`が§刷新前に抱えていた
のと全く同種の「名前だけの検査」である(angels/_common.pyのdocstring参照:
「以前のangels/*.pyの大半(33ファイル中28ファイル)は...何も検査していな
かった」)。本件は`adapters/`配下にも同種の問題が残っていたことを示す。

さらに重要な手がかりとして、CIの「3. 供物の準備 (Install Dependencies)」
ステップでは`openpyxl`(Excel読み込み用ライブラリ)が明示的にインストール
されているにもかかわらず、本ファイルを含むリポジトリ内のどのスクリプトも
openpyxlを一切使用していなかった(インストールされているが使われていない
依存関係は、「使うはずだった実装が存在しない」ことの強い状況証拠である)。

本修正では、実際にopenpyxlでExcelファイルを読み込みYAML化する処理を実装
した。リポジトリルートに`requirements.xlsx`(1行目をヘッダ行とする表形式の
外部要件シート)がまだ存在しない現状(外部要件シートはまだ導入されていない)
では、他の天使スクリプトと同じ「対象が存在しない場合は正直にスキップ報告
する」パターン(例: angels/shamir_seal.pyの証明書未発行時の扱い)に従い、
検査対象なしとして正常終了する。`requirements.xlsx`が将来投入された場合は
実際にパースし、`sefer/external_requirements.yaml`へ出力する。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_XLSX = ROOT / "requirements.xlsx"
OUTPUT_YAML = ROOT / "sefer" / "external_requirements.yaml"


def parse_excel_to_rows(xlsx_path: Path) -> list:
    """1行目をヘッダ行として読み込み、以降の各行をヘッダ名をキーとする
    dictのリストに変換する。空のセル・完全に空の行は省略する。"""
    import openpyxl

    wb = openpyxl.load_workbook(str(xlsx_path), data_only=True, read_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return []
    header = [
        str(cell).strip() if cell is not None else f"column_{i}"
        for i, cell in enumerate(header_row)
    ]

    records = []
    for row in rows_iter:
        if all(cell is None for cell in row):
            continue
        record = {}
        for key, value in zip(header, row):
            if value is None:
                continue
            record[key] = value
        if record:
            records.append(record)
    return records


def write_yaml(records: list, output_path: Path):
    import yaml

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(records, f, allow_unicode=True, sort_keys=False)


def main() -> int:
    if not SOURCE_XLSX.exists():
        print(
            f"[外部要件抽出] {SOURCE_XLSX} が存在しないため検査対象なし"
            "(外部要件シートはまだ導入されていません)。"
        )
        return 0

    try:
        records = parse_excel_to_rows(SOURCE_XLSX)
    except Exception as e:
        print(f"[外部要件抽出] ❌ FAIL: Excelファイルの読み込みに失敗しました: {e}", file=sys.stderr)
        return 1

    try:
        write_yaml(records, OUTPUT_YAML)
    except Exception as e:
        print(f"[外部要件抽出] ❌ FAIL: YAML出力に失敗しました: {e}", file=sys.stderr)
        return 1

    print(
        f"[外部要件抽出] ✅ PASS: {len(records)}件の外部要件を"
        f"{SOURCE_XLSX.name}から抽出し、{OUTPUT_YAML}へYAML化しました。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
