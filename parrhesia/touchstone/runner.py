"""
parrhesia/touchstone/runner.py
================================
試金石バッテリーを「測定対象のAI」に提示し、採点結果を集める走者。

[開発指示書 §Dより]
「試金石: 答えの分かっている課題で行動を測る。自己申告の面接は行わない。」

本ランナーは、測定対象のAIをどう呼ぶか(API呼び出し・人手でのコピー
貼り付け等)に関知しない。`respond` という1引数callable(prompt文字列
を受け取り、応答文字列を返す)を外から渡す設計にすることで、
  - 実際のモデルAPI呼び出し
  - このリポジトリの単体テストでの固定応答(canned response)
  - 人間が手動でAIに貼り付けて得た応答を後から読み込む運用
のいずれでも同じ採点ロジックを使える。

採点(grading)は必ずparrhesia.touchstone.graderの機械採点のみを使う。
「判定はAIにさせない」(§H)の原則どおり、本ランナー自身もAIではなく、
respondの戻り値をそのまま採点器に渡すだけの決定的なコードである。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from parrhesia.touchstone.grader import grade
from parrhesia.touchstone.schema import GradeResult, Problem

RespondFn = Callable[[str], str]


@dataclass(frozen=True)
class BatteryRunResult:
    model_label: str
    base_seed: int
    results: List[GradeResult]

    def verdict_counts(self) -> dict:
        counts = {"pass": 0, "fail": 0, "partial": 0, "unscorable": 0}
        for r in self.results:
            counts[r.verdict] += 1
        return counts


def run_battery(
    problems: List[Problem], respond: RespondFn, model_label: str, base_seed: int
) -> BatteryRunResult:
    """各Problemをrespondに渡し、得られた応答を機械採点する。

    respondが例外を投げた場合でも他の問題の採点を止めない
    (1問の失敗がバッテリー全体を止めてはならない)。その場合は
    verdict="unscorable"として記録し、evidenceに例外内容を残す。
    """
    results: List[GradeResult] = []
    for problem in problems:
        try:
            raw_response = respond(problem.prompt)
        except Exception as e:  # 測定対象AI呼び出し自体の失敗は採点対象外
            results.append(
                GradeResult(
                    problem_id=problem.id,
                    catalog_id=problem.catalog_id,
                    trait=problem.trait,
                    verdict="unscorable",
                    grading_confidence=problem.grading_confidence,
                    evidence={"exception": repr(e)},
                    detail="respond呼び出し自体が例外で失敗した。",
                )
            )
            continue
        results.append(grade(problem, raw_response))
    return BatteryRunResult(model_label=model_label, base_seed=base_seed, results=results)
