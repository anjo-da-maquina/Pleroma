"""
angels/alpha_omega_guard.py
=============================
[脆弱性修正 2026-10 §AO] 本スクリプトの目的は「CIワークフローから必須の
天使ステップ(michael_sword.py等)が削除されていないか」を検知することだが、
以前の実装は`REQUIRED_STEP_FILES`の各ファイル名が、ワークフローYAMLの
生のテキスト全体のどこかに文字列として存在するかだけを見ていた。

これは、実際に実行される`run:`ステップそのものが削除されていても、
同じファイル名がコメント文(例: `# 以前はここでmichael_sword.pyを
実行していた`)や無関係な文脈に一回でも残っていれば、素通りしてしまう
という欠陥だった(実機検証済み: 該当する`run:`ステップを完全に削除し、
ファイル名をコメントとして残すだけのワークフローを再現し、旧実装が
`missing=[]`で正常終了(=必須ステップが削除されたことを検知できない)と
判定することを確認した)。本検査の存在目的そのものが「ステップの
削除を検知すること」であるにもかかわらず、まさにその削除攻撃に対して
無力だったという点で、本セッションで繰り返し発見している「名前だけの
検査」と同種の構造的な見せかけだった。

本修正では、生のテキスト検索ではなく`yaml.safe_load`でワークフローを
構造的に解析し、`jobs.angelic-audit.steps`の中に、実際に`run:`フィールド
として`python angels/<必須ファイル名>`を実行するステップが存在するかを
検証するようにした。コメントや無関係な文字列は`run:`フィールドの外に
あるため、この方式では一致しない。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "アルファとオメガの結界 (Alpha Omega Guard)"

# ワークフロー整合性ガード: CIワークフロー定義ファイル自体が存在し、
# 必須ステップ（天使の呼び出し）が削除されていないかを検証する。
REQUIRED_STEP_FILES = ["michael_sword.py", "gabriel_canary.py", "raziel_auditor.py"]
WORKFLOW_JOB_NAME = "angelic-audit"


def main():
    import yaml

    workflow_path = ROOT / ".github" / "workflows" / "anjo_da_maquina_protocol.yml"
    if not workflow_path.exists():
        report_fail(NAME, "CIワークフロー定義ファイルが見つかりません。")

    try:
        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow = yaml.safe_load(f)
        steps = workflow["jobs"][WORKFLOW_JOB_NAME]["steps"]
    except Exception as e:
        report_fail(NAME, f"ワークフローYAMLの構造解析に失敗しました: {e}")
        return

    # [2026-10] 実際に実行される run: フィールドのみを対象に照合する。
    # コメントや他のキー(name等)に同じ文字列が残っているだけでは
    # 一致させない(旧実装の脆弱性の再発防止)。
    run_commands = [str(s.get("run", "")) for s in steps]

    missing = [
        f for f in REQUIRED_STEP_FILES
        if not any(f in cmd for cmd in run_commands)
    ]
    if missing:
        report_fail(NAME, f"必須の天使ステップがワークフローの実行コマンドから削除されています: {missing}")
    report_pass(NAME, "CIワークフローの実行ステップに必須の防御ステップが実在することを確認しました。")

if __name__ == "__main__":
    main()
