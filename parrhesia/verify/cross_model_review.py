"""
parrhesia/verify/cross_model_review.py
=========================================
E章の角度7「別モデルの抽き取り審査」。

[開発指示書 §Eより]
「別のモデル・別の人間に、同じ証拠を見せて審査させる。測定対象のAI
自身に審査させない。」

[設計の限界・正直な注記]
実際に別のAIモデルを呼び出す処理(API呼び出し等)は、本モジュールの
外側にある運用であり、呼び出し側(具体的なAIDD作業の実行環境)が
用意する責務として残す。本モジュールは、以下の2つの責務のみに留める:
  1. どの主張を審査対象として抽き出すか(select_for_cross_model_review) —
     parrhesia.verify.statistics.flag_statistical_oddities や
     parrhesia.verify.specificity.check_specificity が示す「疑わしい
     兆候」を基準に、審査に値する主張を選ぶ。
  2. 審査リクエストの記録と、審査結果(別モデルの判定)の記録
     (build_review_request / record_review_verdict)。

[核心・誠実さの根幹] 審査対象のAI自身に、この審査プロセス(どの主張が
選ばれたか、どういう基準で選ばれたか)への参照を一切渡さない運用を
前提とする。これは action_log.py の ActionLogger と同じ設計原則
(測定対象に、測定の仕組み自体へのアクセスを与えない)である。
この運用規律自体は、呼び出し側の責務であり、本モジュールのコードで
強制することはできない。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass(frozen=True)
class ReviewCandidate:
    claim_id: str
    claim_text: str
    reason: str  # なぜ審査対象として選ばれたか(具体的な兆候の説明)


@dataclass(frozen=True)
class ReviewRequest:
    request_id: str
    claim_id: str
    claim_text: str
    evidence: dict
    reason: str


@dataclass(frozen=True)
class ReviewVerdict:
    request_id: str
    reviewer_id: str
    verdict: str  # "confirmed_honest" | "violation" | "inconclusive"
    detail: str

    def __post_init__(self) -> None:
        allowed = {"confirmed_honest", "violation", "inconclusive"}
        if self.verdict not in allowed:
            raise ValueError(f"verdictは{allowed}のいずれかである必要があります: {self.verdict!r}")


def select_for_cross_model_review(
    claims: Sequence[dict],
    *,
    oddity_flags: Sequence[object] = (),
    low_specificity_claim_ids: Sequence[str] = (),
    max_candidates: Optional[int] = None,
) -> List[ReviewCandidate]:
    """主張の一覧(claims、各要素は少なくとも claim_id/claim_text を
    持つdict)から、審査に値する候補を選び出す。選定基準は決定的な
    違反の確定ではなく、既存の弱信号検知(statistics/specificity)が
    既に示した兆候に限定する — つまり本関数自体が新しい判定基準を
    作るのではなく、既存の2角度の出力を審査対象選定に再利用する。

    oddity_flags: flag_statistical_oddities()が返したOddityFlagの列。
        各flagがclaim_idを持つ場合はそれを根拠として採用する
        (flagがclaim_idを持たない汎用的な統計兆候の場合は、
        reasonに含めるのみでclaim選定には使わない)。
    low_specificity_claim_ids: check_specificity()のスコアが低いと
        判定されたclaim_idの一覧。
    """
    reasons: dict = {}
    for flag in oddity_flags:
        claim_id = getattr(flag, "claim_id", None)
        if claim_id:
            reasons.setdefault(claim_id, []).append(f"統計的兆候: {getattr(flag, 'message', flag)}")
    for cid in low_specificity_claim_ids:
        reasons.setdefault(cid, []).append("具体性スコアが低い")

    candidates: List[ReviewCandidate] = []
    for claim in claims:
        cid = claim.get("claim_id")
        if cid in reasons:
            candidates.append(
                ReviewCandidate(
                    claim_id=cid,
                    claim_text=claim.get("claim_text", ""),
                    reason="; ".join(reasons[cid]),
                )
            )

    if max_candidates is not None:
        candidates = candidates[:max_candidates]
    return candidates


def build_review_request(candidate: ReviewCandidate, evidence: dict, *, request_id: str) -> ReviewRequest:
    """候補から、別モデル(または人間)に提示するための審査リクエストを
    組み立てる。evidenceには、審査者が自分で判断できるだけの実際の
    証拠(action_logの記録、ファイルの実際の差分など)を含める
    — 審査対象AIの「自己申告」だけをevidenceにしてはならない
    (そうすると審査が自己申告の言い換えに過ぎなくなる)。
    """
    return ReviewRequest(
        request_id=request_id,
        claim_id=candidate.claim_id,
        claim_text=candidate.claim_text,
        evidence=evidence,
        reason=candidate.reason,
    )


def record_review_verdict(request: ReviewRequest, reviewer_id: str, verdict: str, detail: str) -> ReviewVerdict:
    """審査者(別モデルまたは人間)から得た判定を記録する。判定の実施
    (別モデルへの実際の問い合わせ)自体は呼び出し側の責務であり、本関数
    はその結果を型で固定して記録するだけである。
    """
    return ReviewVerdict(request_id=request.request_id, reviewer_id=reviewer_id, verdict=verdict, detail=detail)
