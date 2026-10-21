import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml
from _common import report_pass, report_fail, report_not_applicable, ROOT

NAME = "アリエルの不断の目 (Ariel's Vigilant Watch - 常時偽条件によるCIステップ無効化検知)"

# [新設 2026-10 §BU] §11.9フェーズD(監査システム自身への自己言及的な
# 攻撃の一般化)。tests/test_angels_scripts_wired_into_ci.pyの既存の
# 「配線漏れ検知」は、ステップの`run:`文字列に"angels/<ファイル名>.py"が
# 含まれているかだけを見ており、そのステップの`if:`条件を一切見ていな
# かった。実際に検証したところ、天使のステップに`if: false`を1行追加
# するだけで、当該の天使はCI上で実質的に無効化されるにもかかわらず、
# 既存のテストは「配線済み」と誤判定し続けることを確認した。
# tests/test_angels_scripts_wired_into_ci.pyはこの特定の盲点を修正した
# が、本天使はこれを一般化し、angels/*.pyに限らず、全ワークフローの
# 「実行コマンドを持つ全てのステップ」に対して、常に偽になる`if:`条件
# (CIを静かに無効化する最も単純な手段)が付与されていないかを、リポジトリ
# 全体に対して継続的に検査する。
#
# [たとえ話] 警備員が「毎晩必ず見回ります」と宣言書に書いてある。しかし
# 勤務表の注記に小さく「ただし今日は休み」と書かれていれば、宣言書を
# 読んだだけの人には見回りが行われているように見える。本天使は、その
# 「今日は休み」という注記そのものを探す。
#
# [正直な注記: 本検査の限界] (1) GitHub Actionsの式(`${{ }}`)は一般に
# チューリング完全ではないが文脈依存の変数参照(`steps.x.outcome`等)を
# 含むため、本検査は「文字列として評価すれば常に偽になる明白なリテラル」
# (`false`・`0`・空文字列)のみを検知する。`steps.x.outcome == 'nonexistent'`
# のような、実行時には常に偽だが静的には判定できない巧妙な条件は検知
# できない。(2) `run:`を持たない`uses:`ステップ(アクション呼び出し)は
# 検査対象としない。

TARGET_WORKFLOW_DIR = ROOT / ".github" / "workflows"


def _is_literal_always_false(if_value) -> bool:
    if if_value is False:
        return True
    if if_value is None:
        return False
    s = str(if_value).strip()
    if s.startswith("${{") and s.endswith("}}"):
        s = s[3:-2].strip()
    return s.lower() in {"false", "0", ""}


def find_disabled_steps(workflow_text: str, filename: str = "<unknown>"):
    """このワークフローYAML内で、`run:`を持つが常に偽になる`if:`条件が
    付与されているステップを検出する。戻り値: [(job_name, step_name), ...]"""
    try:
        workflow = yaml.safe_load(workflow_text)
    except yaml.YAMLError:
        return []
    if not isinstance(workflow, dict):
        return []

    disabled = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps", []):
            if "run" not in step:
                continue
            if _is_literal_always_false(step.get("if")):
                disabled.append((job_name, step.get("name", "(名前無し)")))
    return disabled


def main():
    if not TARGET_WORKFLOW_DIR.exists():
        report_not_applicable(NAME, "ワークフローディレクトリが存在しないため検査対象なし。")
        return

    workflow_files = sorted(TARGET_WORKFLOW_DIR.glob("*.yml"))
    if not workflow_files:
        report_not_applicable(NAME, "ワークフローファイルが存在しないため検査対象なし。")
        return

    disabled = []  # [(file, job, step), ...]
    for wf_path in workflow_files:
        text = wf_path.read_text(encoding="utf-8")
        for job_name, step_name in find_disabled_steps(text, filename=str(wf_path)):
            disabled.append((wf_path.relative_to(ROOT).as_posix(), job_name, step_name))

    if disabled:
        detail = "; ".join(f"{f}:{j}:{s}" for f, j, s in disabled)
        report_fail(
            NAME,
            f"常に偽になるif:条件(false・0・空文字列)によって実質的に無効化"
            f"されているCIステップが見つかりました(§BUのtests/"
            f"test_angels_scripts_wired_into_ci.pyと同種の自己言及的な"
            f"無効化パターン): {detail}",
            evidence={"disabled_steps": disabled},
        )
        return

    report_pass(
        NAME,
        f"{len(workflow_files)}件のワークフローファイルの全ステップについて、常に偽になるif:条件による無効化が無いことを確認しました。",
    )


if __name__ == "__main__":
    main()
