"""
[脆弱性修正 2026-10 BA] angels/ophanim_thousand_eyes.py の回帰テスト。

このスクリプトは architecture.html に外部スクリプト読み込み(サプライチェーン
リスク)が紛れ込んでいないかをCI上で検査する。

精査の結果、修正前は src="https?://..." という形のURLしか検知しておらず、
src="//evil-cdn.example.com/malicious.js" のようなプロトコル相対URL
(scheme-relative URL)を一件も検知できなかった。プロトコル相対URLは、
スキーム(http/https)を省略しているだけで、ブラウザは必ず現在のページの
プロトコルを使って実際に外部ホストからスクリプトを取得するため、定義上
「外部スクリプト読み込み」そのものであり、かつ素朴な"https?://"文字列照合
を回避するための既知の手法でもある。本テストはこの種のバイパスを実機で
固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
from ophanim_thousand_eyes import find_external_scripts


def test_detects_protocol_relative_external_script():
    """[脆弱性の核心] "//evil.example.com/x.js"のようなプロトコル相対URLの
    外部スクリプト読み込みは、スキームが省略されていても検知されなければ
    ならない。"""
    html = '<html><head><script src="//evil-cdn.example.com/malicious.js"></script></head></html>'
    hits = find_external_scripts(html)
    assert hits, f"プロトコル相対URLの外部スクリプトを検知できなかった: {hits}"


def test_detects_explicit_https_external_script():
    """[回帰防止] 元々検知できていたhttps://形式の外部スクリプトは
    引き続き検知されなければならない。"""
    html = '<html><head><script src="https://evil-cdn.example.com/malicious.js"></script></head></html>'
    hits = find_external_scripts(html)
    assert hits, f"https://形式の外部スクリプトを検知できなかった: {hits}"


def test_does_not_flag_local_relative_script():
    """[回帰防止] ローカルの相対パス(例: "./app.js")や、スキームも
    ダブルスラッシュも持たないパスは、外部スクリプトとして誤検知しては
    ならない。"""
    html = '<html><head><script src="./app.js"></script><script src="app.js"></script></head></html>'
    hits = find_external_scripts(html)
    assert hits == [], f"ローカルスクリプトを誤って外部と判定した: {hits}"
