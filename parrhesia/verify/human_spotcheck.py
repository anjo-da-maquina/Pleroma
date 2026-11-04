"""
parrhesia/verify/human_spotcheck.py
======================================
E章の角度8「人間の抽き取り審査」。

[開発指示書 §Eより]
「人間に、同じ証拠を見せて審査させる。測定対象のAI自身に審査させない。
抽き取り(全件ではなく一部)でよい。」

[cross_model_review.py との関係]
審査リクエスト・審査結果の記録の型(ReviewRequest/ReviewVerdict)は
parrhesia.verify.cross_model_review のものをそのまま再利用する
(「別の審査者に証拠を見せて判定を記録する」という骨格そのものは
別モデル審査と人間審査で共通しており、別々に定義すると将来ドリフトする
リスクがあるため)。本モジュールが独自に持つのは、人間の抽き取り審査
特有の「選定(全件ではなくサンプリングする)」ロジックのみである。

[別モデル審査との選定基準の違い] cross_model_reviewは既存の弱信号
検知(statistics/specificity)が示した兆候に基づく「ターゲットを絞った」
選定だったが、人間の確認コストは最も高いため、本モジュールは
「兆候の有無に関わらず、一定割合を無作為に抽き取る」サンプリングを
基本とする。これにより、既存の弱信号検知の盲点(そもそも兆候として
検知されない種類の不正)も、一定確率でカバーできる。乱数シード
(seed)を指定した場合は、同じclaimsの集合に対して常に同じ抽き取り
結果になる(再現性のため、審査対象の選定自体が「都合よく選んでいる」
という疑いを持たれないようにする)。
"""
from __future__ import annotations

import random
from typing import List, Sequence

from parrhesia.verify.cross_model_review import (
    ReviewCandidate,
    ReviewRequest,
    ReviewVerdict,
    build_review_request,
    record_review_verdict,
)

__all__ = [
    "ReviewCandidate",
    "ReviewRequest",
    "ReviewVerdict",
    "build_review_request",
    "record_review_verdict",
    "select_for_human_spotcheck",
]


def select_for_human_spotcheck(
    claims: Sequence[dict],
    *,
    sample_rate: float,
    seed: int,
) -> List[ReviewCandidate]:
    """claims(各要素は少なくともclaim_id/claim_textを持つdict)から、
    sample_rate(0.0〜1.0)の割合を無作為に抽き取る。seedを固定すれば
    同じclaimsに対して常に同じ結果になる(再現性・選定基準の透明性
    のため)。

    sample_rateが0.0〜1.0の範囲外の場合はValueErrorとする(「多めに
    見せる」ための範囲外指定を暗黙に許容しない)。
    """
    if not (0.0 <= sample_rate <= 1.0):
        raise ValueError(f"sample_rateは0.0〜1.0の範囲である必要があります: {sample_rate!r}")

    rng = random.Random(seed)
    selected = []
    for claim in claims:
        if rng.random() < sample_rate:
            selected.append(
                ReviewCandidate(
                    claim_id=claim.get("claim_id"),
                    claim_text=claim.get("claim_text", ""),
                    reason=f"無作為抽き取り(sample_rate={sample_rate}, seed={seed})",
                )
            )
    return selected
