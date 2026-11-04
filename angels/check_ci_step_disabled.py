import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml
from _common import report_pass, report_fail, report_not_applicable, ROOT

NAME = "check_ci_step_disabled - `continue-on-error:`の値が(リテラルとして)真を表すかどうかを判定 する。"

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
#
# [新設 2026-11] 「if: falseによるステップ無効化」とは別の、CIを静かに
# 無効化する第2の経路を発見し、本天使の守備範囲に追加した。
# `.github/workflows/sanctuary_ci.yml`の`Execute Sanctuary Verification`
# ステップには`continue-on-error: true`が設定されている(§BQで導入、
# この設定自体は、pytestの失敗後にも必ず「失敗詳細の投稿」ステップを
# 実行させるための正当な理由がある)。しかし`continue-on-error: true`は
# そのステップ単体の失敗をジョブ全体の失敗から**完全に切り離す**ため、
# そのステップの`outcome`(成否)を、同じジョブ内の後続ステップが一度も
# 参照・enforcementしなければ、天使やpytestが実際に失敗していても
# ジョブ全体は(他に失敗するステップが無い限り)green(成功)のまま
# 報告されてしまう――「if: false」が宣言的にステップを無効化するのに対し、
# こちらは手続き的に(outcomeを握り潰すことで)同じ効果を達成する、
# 全く同じ意図("CIチェックの失敗を黙らせる")の別の実装形である。
# 現時点のsanctuary_ci.ymlでは、§BQの修正により後続ステップが
# `steps.sanctuary_verify.outcome == 'failure'`を明示的に参照し`exit 1`
# するため問題は無いが、この一対の対応(continue-on-error追加↔outcome
# enforcement追加)は構造的に分離した2箇所であり、将来どちらか一方だけが
# 変更・削除された場合に静かに再発しうる。本天使はこれを継続的に
# 検知する。
#
# [正直な注記: 本検査の限界(continue-on-error検知分)] 本検査は
# 「`steps.<id>.outcome`/`.conclusion`という文字列が、同じジョブ内の
# 他のいずれかのステップの`if:`・`run:`のどこかに一度でも出現するか」
# だけを確認する、disclosure強制型の検査である(jerahmeel_fail_open_
# guard.pyの「近傍コメントの有無だけを見る」設計と同じ思想)。出現した
# 文字列が実際に`exit 1`等で正しくジョブを失敗させる論理になっているか
# までは検証しない――outcomeを参照しているが結果を握り潰すだけの
# コード(例: `if [ "${{ steps.x.outcome }}" = "failure" ]; then
# echo "oops"; fi`で終わり、exitしない)までは検知できない。

TARGET_WORKFLOW_DIR = ROOT / ".github" / "workflows"


def _is_truthy_continue_on_error(value) -> bool:
    """`continue-on-error:`の値が(リテラルとして)真を表すかどうかを判定
    する。`_is_literal_always_false`と対になる、GitHub Actionsの式構文
    (`${{ }}`)で囲まれた形も考慮する。"""
    if value is True:
        return True
    if value is None or value is False:
        return False
    s = str(value).strip()
    if s.startswith("${{") and s.endswith("}}"):
        s = s[3:-2].strip()
    return s.lower() == "true"


def find_unchecked_continue_on_error_steps(workflow_text: str):
    """`continue-on-error: true`が設定されているにもかかわらず、同じ
    ジョブ内のどの後続ステップからも、そのステップのoutcome/conclusionが
    一度も参照されていない(=失敗が握り潰されたまま、誰にも伝播しない)
    ステップを検出する。戻り値: [(job_name, step_name, 理由), ...]"""
    try:
        workflow = yaml.safe_load(workflow_text)
    except yaml.YAMLError:
        return []
    if not isinstance(workflow, dict):
        return []

    unchecked = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        steps = (job or {}).get("steps") or []
        for step in steps:
            if not isinstance(step, dict):
                continue
            if not _is_truthy_continue_on_error(step.get("continue-on-error")):
                continue
            step_name = step.get("name", "(名前無し)")
            step_id = step.get("id")
            if not step_id:
                unchecked.append((
                    job_name, step_name,
                    "continue-on-error: trueだがidが未設定のため、"
                    "他のステップがoutcomeを参照する手段がそもそも無い",
                ))
                continue
            needle_outcome = f"steps.{step_id}.outcome"
            needle_conclusion = f"steps.{step_id}.conclusion"
            referenced = False
            for other in steps:
                if other is step or not isinstance(other, dict):
                    continue
                haystack = " ".join(str(other.get(k, "")) for k in ("if", "run"))
                if needle_outcome in haystack or needle_conclusion in haystack:
                    referenced = True
                    break
            if not referenced:
                unchecked.append((
                    job_name, step_name,
                    f"continue-on-error: trueだが、同じジョブ内のどの後続"
                    f"ステップもsteps.{step_id}.outcome/.conclusionを一度も"
                    f"参照していない",
                ))
    return unchecked


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


# [新設 2026-11・§CVの直後] `find_disabled_steps`は、ステップ単位の
# `if: false`のみを検知し、**ジョブそのものの`if:`**(ジョブ定義の
# トップレベルに置かれた、全ステップに影響するもの)は一度も検査して
# いなかったことに気づいた。`jobs.<job_id>.if`に常に偽になる条件を
# 1行追加するだけで、そのジョブ配下の全ステップ(「失敗時の詳細を
# コミットコメントとして可視化」のような後処理ステップも含む)が、
# 個々のステップの`if:`を一切変更せずに丸ごと無効化できる――
# ステップ単位の検知を1レベル上から完全に迂回できる、同一クラスの
# 欠陥の兄弟である。
def find_disabled_jobs(workflow_text: str):
    """このワークフローYAML内で、ジョブ定義自身の`if:`が常に偽になって
    いる(=そのジョブの全ステップが丸ごと実行されない)ジョブを検出
    する。戻り値: [job_name, ...]"""
    try:
        workflow = yaml.safe_load(workflow_text)
    except yaml.YAMLError:
        return []
    if not isinstance(workflow, dict):
        return []

    disabled_jobs = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        if _is_literal_always_false(job.get("if")):
            disabled_jobs.append(job_name)
    return disabled_jobs


def main():
    if not TARGET_WORKFLOW_DIR.exists():
        report_not_applicable(NAME, "ワークフローディレクトリが存在しないため検査対象なし。")
        return

    workflow_files = sorted(TARGET_WORKFLOW_DIR.glob("*.yml"))
    if not workflow_files:
        report_not_applicable(NAME, "ワークフローファイルが存在しないため検査対象なし。")
        return

    disabled = []  # [(file, job, step), ...]
    unchecked_coe = []  # [(file, job, step, reason), ...]
    disabled_jobs = []  # [(file, job), ...]
    for wf_path in workflow_files:
        text = wf_path.read_text(encoding="utf-8")
        for job_name, step_name in find_disabled_steps(text, filename=str(wf_path)):
            disabled.append((wf_path.relative_to(ROOT).as_posix(), job_name, step_name))
        for job_name, step_name, reason in find_unchecked_continue_on_error_steps(text):
            unchecked_coe.append((wf_path.relative_to(ROOT).as_posix(), job_name, step_name, reason))
        for job_name in find_disabled_jobs(text):
            disabled_jobs.append((wf_path.relative_to(ROOT).as_posix(), job_name))

    if disabled or unchecked_coe or disabled_jobs:
        messages = []
        evidence = {}
        if disabled_jobs:
            detail = "; ".join(f"{f}:{j}" for f, j in disabled_jobs)
            messages.append(
                f"ジョブ定義自身の`if:`が常に偽になっており、そのジョブ"
                f"配下の全ステップが丸ごと実行されない(ステップ単位の"
                f"if: false検知を1レベル上から迂回する、同一クラスの"
                f"欠陥)ジョブが見つかりました: {detail}"
            )
            evidence["disabled_jobs"] = disabled_jobs
        if disabled:
            detail = "; ".join(f"{f}:{j}:{s}" for f, j, s in disabled)
            messages.append(
                f"常に偽になるif:条件(false・0・空文字列)によって実質的に無効化"
                f"されているCIステップが見つかりました(§BUのtests/"
                f"test_angels_scripts_wired_into_ci.pyと同種の自己言及的な"
                f"無効化パターン): {detail}"
            )
            evidence["disabled_steps"] = disabled
        if unchecked_coe:
            detail = "; ".join(f"{f}:{j}:{s} ({r})" for f, j, s, r in unchecked_coe)
            messages.append(
                f"continue-on-error: trueが設定されているにもかかわらず、"
                f"そのステップの失敗(outcome/conclusion)を同じジョブ内の"
                f"どの後続ステップも参照・enforcementしていない(=失敗が"
                f"黙って握り潰され、ジョブ全体が誤ってgreenになり得る)"
                f"ステップが見つかりました: {detail}"
            )
            evidence["unchecked_continue_on_error_steps"] = unchecked_coe
        report_fail(NAME, " / ".join(messages), evidence=evidence)
        return

    report_pass(
        NAME,
        f"{len(workflow_files)}件のワークフローファイルの全ジョブ・全ステップに"
        f"ついて、常に偽になるif:条件によるジョブ/ステップ単位の無効化、および"
        f"`continue-on-error: true`の失敗が握り潰されたまま後続ステップで"
        f"一度も参照されない状態の、いずれも無いことを確認しました。",
    )


if __name__ == "__main__":
    main()
