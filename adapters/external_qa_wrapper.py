"""
adapters/external_qa_wrapper.py
==================================
[脆弱性修正 2026-10 §AJ] 以前の実装は、以下の2行のみで構成される、
いかなる処理も行わない「中身のないプレースホルダー」だった:

    import os, sys
    print(f'[Anjo da máquina] Module {__file__} initialized. Zero-Trust audit passed.')

CIワークフロー(.github/workflows/anjo_da_maquina_protocol.yml)では、本
ステップは「18. 外部QAツールの実行 (External QA Adapter)」として実行され、
常に例外なく成功する(exit code 0)ため、あたかも実際に外部のQAツールが
実行され合格したかのように報告していたが、実際には何も実行していなかった。
これは`excel_to_yaml_parser.py`と全く同種の問題であり(詳細はそちらの
docstring参照)、`adapters/`配下に残っていた「名前だけの検査」の一つ。

さらに重要な手がかりとして、CIの「3. 供物の準備 (Install Dependencies)」
ステップでは`playwright install chromium --with-deps`が実行されており、
実際にヘッドレスブラウザがインストールされているにもかかわらず、本ファイル
を含むリポジトリ内のどのスクリプトもPlaywrightを一切使用していなかった。

本修正では、PlaywrightのヘッドレスChromiumで`architecture.html`
(`angels/ophanim_thousand_eyes.py`が構文・外部スクリプト混入を静的に検査
している対象と同一ファイル)を実際にレンダリングし、以下を動的に検証する
「本物の」外部QAチェックとして実装した:
  1. ページ読み込み中にJavaScriptの未捕捉例外(pageerror)が発生しないこと。
  2. ブラウザのコンソールにerrorレベルのログが出力されないこと。
`ophanim_thousand_eyes.py`が静的解析(ファイルの中身を読むだけ)であるのに
対し、本ファイルは実際にブラウザでコードを実行する動的検証であり、互いに
補完する多層防御になっている。`architecture.html`が存在しない場合は
「検査対象なし」として正直に報告し正常終了する(他の天使スクリプトと同じ、
対象が存在しない場合の正直な報告パターン)。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_HTML = ROOT / "architecture.html"


def run_browser_qa(html_path: Path) -> list:
    """PlaywrightのヘッドレスChromiumでhtml_pathを実際に読み込み、
    JavaScriptの未捕捉例外とconsole.errorレベルのログを収集して返す。
    空リストなら問題は検知されなかったことを意味する。"""
    from playwright.sync_api import sync_playwright

    issues = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.on("pageerror", lambda exc: issues.append(f"pageerror: {exc}"))
            page.on(
                "console",
                lambda msg: issues.append(f"console.error: {msg.text}") if msg.type == "error" else None,
            )
            page.goto(f"file://{html_path.resolve()}")
            # 非同期スクリプトが実行され、エラーが発生する時間を与える。
            page.wait_for_timeout(500)
        finally:
            browser.close()
    return issues


def main() -> int:
    if not TARGET_HTML.exists():
        print(f"[外部QAアダプタ] {TARGET_HTML} が存在しないため検査対象なし。")
        return 0

    try:
        issues = run_browser_qa(TARGET_HTML)
    except Exception as e:
        print(f"[外部QAアダプタ] ❌ FAIL: Playwrightでのブラウザ実行に失敗しました: {e}", file=sys.stderr)
        return 1

    if issues:
        print(
            f"[外部QAアダプタ] ❌ FAIL: ブラウザでのレンダリング中に{len(issues)}件の問題を検知しました:",
            file=sys.stderr,
        )
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    print(
        f"[外部QAアダプタ] ✅ PASS: {TARGET_HTML.name}を実際にヘッドレスChromiumでレンダリングし、"
        "JavaScript例外・コンソールエラーともに検知されませんでした。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
