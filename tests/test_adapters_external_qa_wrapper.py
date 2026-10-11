"""
tests/test_adapters_external_qa_wrapper.py
=============================================
adapters/external_qa_wrapper.py の回帰テスト。GRIMOIRE.md §AJ 参照。

背景: 本ファイルは以前
    import os, sys
    print(f'[Anjo da máquina] Module {__file__} initialized. Zero-Trust audit passed.')
のみで構成される、いかなる処理も行わない「中身のないプレースホルダー」
だった。CIでは「外部QAツールの実行 (External QA Adapter)」として常に
無条件に成功を報告していたが、実際にブラウザでコードを実行したことは
一度もなかった。本テストは、実際にPlaywrightのヘッドレスChromiumで
HTMLをレンダリングし、JavaScriptの例外・コンソールエラーを本当に検知
できることを固定する。

[注意] 本テストはPlaywrightの実際のブラウザ起動を伴うため、他のテストに
比べて実行時間が長い。本サンドボックス環境ではChromiumがプリインストール
されており(/opt/pw-browsers配下)、追加のダウンロードは発生しない。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "adapters"))

import external_qa_wrapper as qa_mod  # noqa: E402


def _reload_with_target(monkeypatch, target_html: Path):
    monkeypatch.setattr(qa_mod, "TARGET_HTML", target_html)


def test_missing_target_reports_no_target_and_succeeds(tmp_path, monkeypatch):
    """[脆弱性修正の核心] architecture.htmlが存在しない場合、偽の
    "Zero-Trust audit passed"を名乗ってはならず、正直に検査対象なしを
    報告して正常終了(exit code 0)しなければならない。"""
    target = tmp_path / "architecture.html"
    _reload_with_target(monkeypatch, target)
    assert qa_mod.main() == 0


def test_clean_html_passes_browser_qa(tmp_path, monkeypatch):
    """[脆弱性修正の核心] JavaScriptエラーの無い正常なHTMLは、実際に
    ヘッドレスChromiumでレンダリングされ、問題なしと判定されなければ
    ならない。"""
    target = tmp_path / "architecture.html"
    target.write_text(
        "<!DOCTYPE html><html><head><title>OK</title></head>"
        "<body><script>var x = 1 + 1;</script></body></html>",
        encoding="utf-8",
    )
    _reload_with_target(monkeypatch, target)
    assert qa_mod.main() == 0


def test_uncaught_js_exception_is_actually_detected(tmp_path, monkeypatch):
    """[脆弱性修正の核心] 旧実装は何も実行しなかったため、意図的に埋め込んだ
    JavaScriptの未捕捉例外すら検知できなかった。本修正後は、実際にブラウザ
    で実行してpageerrorとして検知しなければならない。"""
    target = tmp_path / "architecture.html"
    target.write_text(
        "<!DOCTYPE html><html><body>"
        "<script>throw new Error('deliberate test error');</script>"
        "</body></html>",
        encoding="utf-8",
    )
    _reload_with_target(monkeypatch, target)
    assert qa_mod.main() == 1


def test_console_error_is_actually_detected(tmp_path, monkeypatch):
    """console.error()への出力も、ブラウザでの実行結果として検知されな
    ければならない。"""
    target = tmp_path / "architecture.html"
    target.write_text(
        "<!DOCTYPE html><html><body>"
        "<script>console.error('something went wrong');</script>"
        "</body></html>",
        encoding="utf-8",
    )
    _reload_with_target(monkeypatch, target)
    assert qa_mod.main() == 1
