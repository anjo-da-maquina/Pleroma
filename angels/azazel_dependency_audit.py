"""
angels/azazel_dependency_audit.py
====================================
[新設 2026-10] 「サプライチェーン依存の既知脆弱性(CVE)監査」

`angels/ophanim_eye.py`は`requirements.txt`の全依存がバージョン固定(==)
されているかのみを検証する。しかし、バージョンが固定されていても、その
固定された版自体に既知の脆弱性が公表されている可能性は一切検査していない。
本スクリプトは、固定された依存の版そのものを、公開されている脆弱性
データベース(PyPI Advisory Database / OSV.dev、`pip-audit`経由)と
実際に照合する。

[命名の由来] アザゼルは、人間に武器の鍛造技術という「悪用可能な知識」を
教えたとされる堕天使である。本スクリプトが監視する対象もまさに同種の
もの — 既に世に知られてしまった(悪用可能な)脆弱性の知識 — であるため、
この名を当てた。

[誠実に明記する既知の限界]
  1. 本検査は外部のネットワーク通信(脆弱性データベースへの照会)に
     依存する。他の天使の大半が外部通信ゼロで完結する静的解析である
     のに対し、本検査だけは構造的にネットワーク到達性が無ければ
     *何も確認できない*。ネットワークが遮断された環境でこの検査を
     「PASS」として報告することは、「調べていないのに安全だと主張する」
     ことになり、本プロジェクトが繰り返し修正してきた「学習したつもりに
     なっているだけ」の構造的な見せかけと同じ過ちになる。そのため、
     `pip-audit`自体の実行(DBへの照会を含む)が失敗した場合は、
     安全側に倒して検査自体をFAILとして報告する(フェイルクローズド)。
  2. `pip-audit`が知らない、あるいはデータベースに未登録の脆弱性
     (ゼロデイ等)は検知できない。本検査は「既に公表されている既知の
     脆弱性」のみを対象とする。
"""
import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, report_info, ROOT

NAME = "アザゼルの禁断知識 (Azazel Dependency Audit - サプライチェーン既知脆弱性監査)"

REQUIREMENTS_PATH = ROOT / "requirements.txt"


def _ensure_pip_audit_installed() -> bool:
    """pip-auditが無ければインストールを試みる。戻り値はインストール済み
    (または元から利用可能)かどうか。"""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip_audit", "--version"],
            capture_output=True, text=True, check=True,
        )
        return True
    except Exception:
        pass
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "pip-audit"],
            capture_output=True, text=True, check=True, timeout=120,
        )
        subprocess.run(
            [sys.executable, "-m", "pip_audit", "--version"],
            capture_output=True, text=True, check=True,
        )
        return True
    except Exception:
        return False


def main():
    if not REQUIREMENTS_PATH.exists():
        report_pass(NAME, "requirements.txt が存在しないため検査対象なし。")
        return

    if not _ensure_pip_audit_installed():
        report_fail(
            NAME,
            "pip-auditを利用できません(インストール失敗、またはネットワーク"
            "到達性がありません)。既知脆弱性の有無を確認できない以上、"
            "『安全である』とは主張できないため、フェイルクローズドで"
            "検査自体を失敗とします。"
        )
        return

    result = subprocess.run(
        [
            sys.executable, "-m", "pip_audit",
            "-r", str(REQUIREMENTS_PATH),
            "--format", "json",
        ],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300,
    )

    # pip-auditはpipの依存解決自体に失敗した場合など、JSONを一切出力せず
    # 異常終了することがある。この場合もフェイルクローズドとする。
    try:
        report = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        report = None

    if report is None:
        report_fail(
            NAME,
            f"pip-auditの実行結果を解析できませんでした(終了コード={result.returncode})。"
            f"\n--- stdout ---\n{result.stdout[:2000]}\n--- stderr ---\n{result.stderr[:2000]}"
        )
        return

    # pip-auditのJSON出力形式: {"dependencies": [{"name": ..., "version": ...,
    # "vulns": [{"id": ..., "fix_versions": [...], "description": ...}, ...]}, ...]}
    vulnerable = [
        dep for dep in report.get("dependencies", [])
        if dep.get("vulns")
    ]
    if vulnerable:
        details = [
            f"{dep['name']}=={dep.get('version', '?')}: "
            f"{[v.get('id') for v in dep['vulns']]}"
            for dep in vulnerable
        ]
        report_fail(
            NAME,
            f"requirements.txtに既知の脆弱性を持つ依存が見つかりました: {details}"
        )
        return

    total_checked = len(report.get("dependencies", []))
    report_pass(
        NAME,
        f"requirements.txtの{total_checked}件の依存全てについて、"
        "既知の脆弱性(pip-audit / OSV.dev)は検出されませんでした。"
    )


if __name__ == "__main__":
    main()
