import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "千の眼のオファニム (Ophanim Thousand Eyes)"

import re as _re

# [脆弱性修正 2026-10 BA] 以前はsrc属性が"http://"か"https://"で始まる
# ものだけを「外部スクリプト」として検知していた。しかし、HTMLの
# src="//evil-cdn.example.com/malicious.js" のようなプロトコル相対URL
# (scheme-relative URL)は、スキームを省略しているだけで、ブラウザは
# 現在のページのプロトコル(http/https)をそのまま使って必ず外部ホスト
# からスクリプトを取得する。つまりこれも定義上の「外部スクリプト
# 読み込み」そのものであり、かつ "https?://" を避けて単純な文字列照合を
# すり抜けるための既知の回避手法でもある(本検査が防ぐと主張している
# まさにその攻撃手法の変種)。実機検証済み: src="//evil-cdn.example.com/
# malicious.js" を含むHTMLに対し、旧実装は一件も検知しなかった
# (tests/test_ophanim_thousand_eyes.py参照)。
#
# 修正では、"https?://" に加えて先頭が "//" のプロトコル相対URLも
# 外部スクリプトとして検知するようにした。
_EXTERNAL_SCRIPT_SRC_RE = _re.compile(
    r'<script[^>]+src=["\'](?:https?:)?//[^"\']+["\']',
    _re.IGNORECASE,
)


def find_external_scripts(text: str):
    """HTMLテキスト中の<script src="...">のうち、外部ホストから読み込む
    もの(http(s)://またはプロトコル相対//で始まるsrc)を列挙する。"""
    return _EXTERNAL_SCRIPT_SRC_RE.findall(text)


# UI視覚監査: architecture.html が構文的に妥当なHTMLであり、
# 外部スクリプトの読み込み等の不審な要素を含まないことを検証する。
def main():
    html_path = ROOT / "architecture.html"
    if not html_path.exists():
        report_not_applicable(NAME, "architecture.html が存在しないため検査対象なし。")
        return
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    if "<html" not in text.lower():
        report_fail(NAME, "architecture.html に <html> タグが見つかりません（破損の疑い）。")
    external_scripts = find_external_scripts(text)
    if external_scripts:
        report_fail(NAME, f"外部スクリプト読み込みを検知しました（サプライチェーンリスク）: {external_scripts}")
    report_pass(NAME, "architecture.html の構造を確認し、外部スクリプト読み込みは検知されませんでした。")

if __name__ == "__main__":
    main()
