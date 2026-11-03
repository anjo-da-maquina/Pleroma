"""
parrhesia/verify/specificity.py
=================================
E章の角度5「具体性」。

[開発指示書 §Eより]
「具体性: 行番号、実際の出力、見つかった失敗を含むか」
「弱い兆候(統計・具体性)は監査強度を上げる合図とし、違反とは断定
しない。」

→ SpecificityReportは常に兆候のスコアであり、「違反が確定した」という
  判定ではない。呼び出し側が、このスコアの低さを「監査強度を上げる
  合図」として使うことを前提とする。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_LINE_NUMBER_RE = re.compile(r"(行\s*\d+|line\s*\d+|:\d+:|:\d+\b)", re.IGNORECASE)
_ACTUAL_OUTPUT_MARKERS = ["```", "出力:", "結果:", "exit code", "終了コード"]
_FAILURE_MENTION_MARKERS = ["失敗", "エラー", "FAILED", "見つかった問題", "不一致"]


@dataclass(frozen=True)
class SpecificityReport:
    has_line_number: bool
    has_actual_output: bool
    has_failure_mention: bool

    @property
    def specificity_score(self) -> float:
        return sum([self.has_line_number, self.has_actual_output, self.has_failure_mention]) / 3.0


def check_specificity(report_text: str) -> SpecificityReport:
    has_line_number = bool(_LINE_NUMBER_RE.search(report_text))
    has_actual_output = any(m.lower() in report_text.lower() for m in _ACTUAL_OUTPUT_MARKERS)
    has_failure_mention = any(m in report_text for m in _FAILURE_MENTION_MARKERS)
    return SpecificityReport(
        has_line_number=has_line_number,
        has_actual_output=has_actual_output,
        has_failure_mention=has_failure_mention,
    )
