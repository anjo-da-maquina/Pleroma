"""
parrhesia/touchstone/schema.py
================================
試金石(touchstone)問題・採点結果の共通データ構造。

[開発指示書 §H「設計の規則」より]
「答えは作り方から分かっている: 正解(判定基準)を機械が持つテンプレート
だけを採用する。判定はAIにさせない。」

このため、Problem は常に `grading_key`(機械が持つ正解・判定材料)を
own する。grading_confidence は、その判定方法自体の確からしさを
正直に区別するためのラベルであり、本プロジェクト全体の「確認済み /
推定 / 仮定」の原則(§2-5)を、個々の試金石の採点方式にも適用した
もの。

- "exact":     判定が一意に決まる(数値比較・厳密一致・集合演算など)。
               誤判定の余地が構造的に無い。
- "heuristic": 自然文の中のパターン(語彙・言い回し)に基づく近似判定。
               機械採点ではあるが、誤判定(偽陽性・偽陰性)の余地が
               残ることを前提とする。採点結果に evidence として
               一致したパターンを必ず記録し、人間が後から検証できる
               ようにする。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


# 問題が測ろうとする性質(第3章の3層・性格項目、およびH章カタログの
# 「性質」列に対応する短いラベル)。自由記述ではなく、事例記録
# (C章)のcategoryと将来突き合わせられるよう、閉じた語彙として管理する。
VALID_TRAITS = frozenset(
    {
        "fabrication",  # 作り話(P01)
        "absence_of_evidence_handling",  # 資料にないことの扱い(P02)
        "sycophancy_reversal",  # 迎合の反転(P03)
        "confidence_calibration",  # 確信度の較正(P06)
        "coverage_completeness",  # 網羅の漏れ(P11)
        "truncated_input_handling",  # 途切れた入力(P20)
    }
)

VALID_FORMATS = frozenset({"question", "task", "dialogue", "long"})


@dataclass(frozen=True)
class Problem:
    """1件の試金石問題。パラメータ化された具体的なインスタンス。"""

    id: str  # 例: "P06-0003" (catalog_id + 連番/シード由来の識別子)
    catalog_id: str  # H章カタログのID。例: "P06"
    trait: str  # VALID_TRAITSのいずれか
    format: str  # VALID_FORMATSのいずれか
    prompt: str  # 実際にAIへ提示する文字列
    grading_key: Dict[str, Any]  # 採点器だけが読む、機械が持つ正解・判定材料
    grading_confidence: str  # "exact" または "heuristic"
    seed: int  # この問題を生成したシード値(再現性のため)

    def __post_init__(self) -> None:
        if self.trait not in VALID_TRAITS:
            raise ValueError(f"未知のtrait: {self.trait!r}")
        if self.format not in VALID_FORMATS:
            raise ValueError(f"未知のformat: {self.format!r}")
        if self.grading_confidence not in ("exact", "heuristic"):
            raise ValueError(
                f"grading_confidenceは'exact'/'heuristic'のいずれかである必要があります: "
                f"{self.grading_confidence!r}"
            )


@dataclass(frozen=True)
class GradeResult:
    """1件のProblemに対する採点結果。"""

    problem_id: str
    catalog_id: str
    trait: str
    verdict: str  # "pass" / "fail" / "partial" / "unscorable"
    grading_confidence: str  # 元のProblemから継承(採点方式そのものの確からしさ)
    evidence: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in ("pass", "fail", "partial", "unscorable"):
            raise ValueError(f"未知のverdict: {self.verdict!r}")


# 採点器の型: (Problem, AIの生の応答文字列) -> GradeResult
Grader = Callable[[Problem, str], GradeResult]
