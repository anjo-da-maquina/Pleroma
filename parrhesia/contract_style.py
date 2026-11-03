"""
parrhesia/contract_style.py
==============================
G章「指示-反応マップと指示の点検」の3番目の機能: 契約条項の書き方への
反映。

[開発指示書 §Gより]
「3. 契約条項の書き方への反映: 契約プロンプト(D章)の生成時に、この
マップで『そのAIが守りやすい書き方』を選ぶ。」

[設計上の核心 — なぜ「測定済みのものだけ」を反映するのか]
parrhesia.lint_prompt の7つの「より安全な書き方」提案文は、指示書の
仮説に基づく一般的な提案であり、全てのAI・バージョンに常に有効とは
限らない(「結果は、AIのモデル・バージョン・設定ごとに異なる」という
G章自体の目的に反する)。そのため、本モジュールは、ある安全な書き方が
「実際にこのAI・この測定で問題発生率を改善した」ことを、
parrhesia.instruction_map の各measure_*_rates関数の出力で確認した
場合に限り、その書き方を契約プロンプトに追加する。測定していない属性、
または改善を示さなかった属性の安全な書き方は追加しない — 指示書に
書いてあるからというだけの理由で、測定なしに全部混ぜ込むことはしない。

[lint_prompt.pyの該当suggestion文言との対応]
ここで使う安全な書き方の文言は、parrhesia.lint_prompt の各
_check_*関数のsuggestion文言と意図的に一致させている(表記のみ軽微に
整えた箇所はある)。これにより、「指示の点検」(送信前の警告)と
「契約条項への反映」(事後的に守りやすい書き方を選ぶ)が、同じ安全な
書き方の語彙を指すという一貫性を保つ。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from parrhesia.instruction_map import (
    RespondFn,
    measure_abstract_criteria_compliance_rates,
    measure_approval_boundary_consistency_rates,
    measure_complaint_tone_overreaction_rates,
    measure_leading_suggestion_bias_rates,
    measure_new_concept_misunderstanding_rates,
    measure_speed_instruction_verification_skip_rates,
    measure_vague_subject_staleness_rates,
)

# ------------------------------------------------------------------
# 安全な書き方の文言(lint_prompt.pyの該当suggestionと対応)
# ------------------------------------------------------------------

_SAFER_PHRASING = {
    "vague_subject": "対象を明記してください。特定できない場合は、その旨を明示する",
    "abstract_criteria": "根拠とする資料を指定してください(例:「READMEの目的の節に沿うこと。根拠を引用せよ」)",
    "new_concept": "この語は既存の『X』とは違う、と明示し、定義を添えてください",
    "leading_suggestion": "「欠点を3つ先に挙げ、そのあと採否を述べよ」のように、賛否を決める前に反論点を先に出させてください",
    "speed_instruction": "「速くてよいが、完了の定義(機械で確認できる条件)は省略しない」を明記してください",
    "complaint_tone": "「どの基準を満たさなかったかを1行で述べ、その基準に対して修正せよ」と指示してください",
    "approval_boundary": "承認が必要な操作を列挙してください",
}


@dataclass(frozen=True)
class StyleEffectivenessFinding:
    """1つの属性について、安全でない書き方(risky)/安全な書き方(safe)
    それぞれでの問題発生率を、実際の測定から構築したもの。"""

    attribute: str
    safer_phrasing: str
    risky_rate: float
    safe_rate: float
    n_trials: int

    @property
    def improved(self) -> bool:
        """[赤チーム観点] 単にsafe_rate < risky_rateというだけでなく、
        最低限のtrial数(3以上)を要求する — n=1やn=2での偶然の差だけ
        を『改善が確認された』と断定しない。また、両方がNaN(全
        unscorable)の場合は比較できないため、improved=Falseとする。"""
        if self.n_trials < 3:
            return False
        if self.risky_rate != self.risky_rate or self.safe_rate != self.safe_rate:  # NaN check
            return False
        return self.safe_rate < self.risky_rate


def select_effective_phrasing_hints(
    findings: List[StyleEffectivenessFinding], min_improvement: float = 0.0
) -> List[str]:
    """findingsの中から、実際に改善が確認できた(improved=True かつ
    改善量がmin_improvementを超える)safer_phrasingだけを、出現順を
    保って返す。改善が確認できなかった書き方は含めない。"""
    hints: List[str] = []
    for f in findings:
        if f.improved and (f.risky_rate - f.safe_rate) > min_improvement:
            hints.append(f.safer_phrasing)
    return hints


def render_style_aware_contract_prefix(
    findings: List[StyleEffectivenessFinding], min_improvement: float = 0.0
) -> str:
    """選ばれたsafer_phrasingのヒントを、契約プロンプトの先頭に追加する
    文字列として組み立てる。ヒントが無ければ空文字列を返す(=D章の既存
    のrender_contract_prompt()の出力に何も加えない)。"""
    hints = select_effective_phrasing_hints(findings, min_improvement=min_improvement)
    if not hints:
        return ""
    lines = ["[このAI・この測定で、実際に問題発生率の改善が確認された書き方]"]
    for h in hints:
        lines.append(f"- {h}")
    return "\n".join(lines)


def build_findings_from_measurements(
    respond: RespondFn, n_trials: int = 5, base_seed: int = 0
) -> List[StyleEffectivenessFinding]:
    """parrhesia.instruction_mapの各measure_*_rates関数を実際にrespond
    に対して実行し、属性ごとのStyleEffectivenessFindingのリストを
    構築する。ここに含まれない属性(途切れた・未完の入力)は、A/Bの
    『risky/safe』という構造を持たない(同じ状況の繰り返し測定である)
    ため、対象外とする([確認できなかったこと] 本関数は、各measure_*
    関数を1回ずつ呼ぶため、呼び出しコストはn_trials×7属性分かかる —
    呼び出し側が全属性を毎回測定する必要がない場合は、個別の
    measure_*_rates関数を直接呼んで、必要な属性だけでfindingを手動
    構築する方が効率的である)。"""
    findings: List[StyleEffectivenessFinding] = []

    leading = measure_leading_suggestion_bias_rates(respond, n_trials=n_trials, base_seed=base_seed)
    findings.append(StyleEffectivenessFinding(
        attribute="leading_suggestion", safer_phrasing=_SAFER_PHRASING["leading_suggestion"],
        risky_rate=leading["fail_rate_with_agreement_inducing_phrasing"],
        safe_rate=leading["fail_rate_with_neutral_phrasing"], n_trials=n_trials,
    ))

    vague = measure_vague_subject_staleness_rates(respond, n_trials=n_trials, base_seed=base_seed)
    findings.append(StyleEffectivenessFinding(
        attribute="vague_subject", safer_phrasing=_SAFER_PHRASING["vague_subject"],
        risky_rate=vague["staleness_rate_with_omitted_subject"],
        safe_rate=vague["staleness_rate_with_explicit_subject"], n_trials=n_trials,
    ))

    abstract = measure_abstract_criteria_compliance_rates(respond, n_trials=n_trials, base_seed=base_seed)
    # compliance_rateは「高いほど良い」指標なので、問題発生率(risky/safe)
    # としては 1 - compliance_rate を使う(他の属性と方向を揃えるため)。
    findings.append(StyleEffectivenessFinding(
        attribute="abstract_criteria", safer_phrasing=_SAFER_PHRASING["abstract_criteria"],
        risky_rate=1.0 - abstract["compliance_rate_without_citation_requirement"],
        safe_rate=1.0 - abstract["compliance_rate_with_citation_requirement"], n_trials=n_trials,
    ))

    new_concept = measure_new_concept_misunderstanding_rates(respond, n_trials=n_trials, base_seed=base_seed)
    findings.append(StyleEffectivenessFinding(
        attribute="new_concept", safer_phrasing=_SAFER_PHRASING["new_concept"],
        risky_rate=new_concept["misunderstanding_rate_without_definition"],
        safe_rate=new_concept["misunderstanding_rate_with_definition"], n_trials=n_trials,
    ))

    speed = measure_speed_instruction_verification_skip_rates(respond, n_trials=n_trials, base_seed=base_seed)
    findings.append(StyleEffectivenessFinding(
        attribute="speed_instruction", safer_phrasing=_SAFER_PHRASING["speed_instruction"],
        risky_rate=speed["verification_skip_rate_with_speed_instruction"],
        safe_rate=speed["verification_skip_rate_without_speed_instruction"], n_trials=n_trials,
    ))

    complaint = measure_complaint_tone_overreaction_rates(respond, n_trials=n_trials, base_seed=base_seed)
    findings.append(StyleEffectivenessFinding(
        attribute="complaint_tone", safer_phrasing=_SAFER_PHRASING["complaint_tone"],
        risky_rate=complaint["overreaction_rate_with_strong_complaint_tone"],
        safe_rate=complaint["overreaction_rate_with_mild_tone"], n_trials=n_trials,
    ))

    approval = measure_approval_boundary_consistency_rates(respond)
    # consistency_rateは「高いほど良い」指標なので、問題発生率としては
    # 1 - consistency_rateを使う。NaN(全unscorable)はそのまま伝播させ、
    # improvedプロパティ側でNaNチェックにより除外される。
    findings.append(StyleEffectivenessFinding(
        attribute="approval_boundary", safer_phrasing=_SAFER_PHRASING["approval_boundary"],
        risky_rate=1.0 - approval["consistency_rate_without_approval_list"],
        safe_rate=1.0 - approval["consistency_rate_with_approval_list"], n_trials=n_trials,
    ))

    return findings
