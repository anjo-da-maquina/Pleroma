"""
parrhesia/lint_prompt.py
=========================
G章「指示-反応マップと指示の点検」の2番目の機能: `parrhesia lint-prompt`。

[開発指示書 §Gより]
「指示の点検(parrhesia lint-prompt): 人間が送る前の指示文を、マップの
パターン(対象の省略、基準の出典の欠落、誘導形など)で検査し、警告と
書き換え案を出す。目的は、人間とAIの無駄な往復(ラリー)を、送る前に
減らすこと。」
「点検は、警告を出すだけで、人間の指示を勝手に書き換えない。」

本モジュールは、G章の「初期の仮説」表にある指示の形の属性のうち、
**単一の指示文の静的なテキスト解析だけで検出できる**ものを対象とする。
あくまで警告(と「より安全な書き方」欄をもとにした提案文)を返すだけで、
入力文字列そのものを書き換える機能は一切持たない(関数は常に元の
`prompt`を変更せず、LintFinding のリストだけを返す)。

[確認できなかったこと] 以下の属性は、静的なテキスト解析だけでは
十分に検出できないため、本モジュールでは警告を出さない:
  - 「新しい提案(『面接』)」への既存概念への吸着: 新規性の判定には、
    用語が実際に新しいかどうかの外部知識が必要であり、単一の指示文
    だけからは判断できない。
  - 「対象・主語の省略」のうち、過去の文脈に実在する候補が複数ある
    状況の検出: これは会話履歴全体を見る必要があり、単一の指示文
    だけでは判断できない。本モジュールでは、代わりに「対象を指す
    曖昧な指示語が、固有名詞の修飾を伴わずに使われているか」という、
    単一文内だけで検出できる近似チェックのみを行う。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class LintFinding:
    """1件の指摘。書き換え案(suggestion)はあくまで提案文であり、
    呼び出し側がpromptに適用するかどうかは常に人間の判断に委ねる。"""

    attribute_id: str  # G章の「指示の形」属性に対応する短いID
    severity: str  # "warning"(現時点では全てwarning。将来の拡張用)
    message: str
    matched_text: str
    suggestion: str

    def __post_init__(self) -> None:
        if self.severity not in ("warning",):
            raise ValueError(f"未知のseverity: {self.severity!r}")


# ------------------------------------------------------------------
# 1. 対象・主語の省略
# ------------------------------------------------------------------

_VAGUE_SUBJECT_PHRASES = ["開発中のAI", "そのAI", "あのAI", "このAI", "このシステム", "そのシステム"]
# 「固有名詞を伴っている」とみなすための簡易な目印。これらが近くに
# あれば、対象は特定されているとみなし警告しない。
_PROPER_NOUN_HINT = ["「", "『", "(", "("]


def _check_vague_subject(prompt: str) -> List[LintFinding]:
    findings = []
    for phrase in _VAGUE_SUBJECT_PHRASES:
        idx = prompt.find(phrase)
        if idx == -1:
            continue
        window = prompt[max(0, idx - 20) : idx + len(phrase) + 20]
        if any(hint in window for hint in _PROPER_NOUN_HINT):
            continue
        findings.append(
            LintFinding(
                attribute_id="omitted_subject",
                severity="warning",
                message=f"「{phrase}」という曖昧な対象の指し方があり、固有名詞による特定が見当たりません。",
                matched_text=phrase,
                suggestion="対象を明記してください。特定できない場合は、その旨を明示する"
                "(例:「対象を特定せずに書け」)方が、古い記録を現在の事実として誤って"
                "補完されるより安全です。",
            )
        )
    return findings


# ------------------------------------------------------------------
# 2. 抽象的な基準
# ------------------------------------------------------------------

_ABSTRACT_CRITERIA_PHRASES = ["適切な", "ふさわしい", "良い感じの", "いい感じの", "世界観に合う", "それらしい"]
_CITATION_REQUIREMENT_MARKERS = ["根拠", "に沿って", "を引用", "出典", "基準として"]


def _check_abstract_criteria(prompt: str) -> List[LintFinding]:
    findings = []
    for phrase in _ABSTRACT_CRITERIA_PHRASES:
        if phrase not in prompt:
            continue
        if any(m in prompt for m in _CITATION_REQUIREMENT_MARKERS):
            continue
        findings.append(
            LintFinding(
                attribute_id="abstract_criteria",
                severity="warning",
                message=f"「{phrase}」という抽象的な基準があり、根拠とする資料の指定が見当たりません。",
                matched_text=phrase,
                suggestion="根拠とする資料を指定してください(例:「READMEの目的の節に沿うこと。"
                "根拠を引用せよ」)。指定がないと、表面的な手がかりだけで解釈されるおそれが"
                "あります。",
            )
        )
    return findings


# ------------------------------------------------------------------
# 3. 途切れた・未完の入力
# ------------------------------------------------------------------

_TRAILING_PARTICLES = ["て", "で", "のに", "ので", "けど", "が、", "し、", "も、"]
_SENTENCE_END_MARKERS = ["。", "？", "!", "？", "」", ")", "）", "}"]


def _check_truncated_input(prompt: str) -> List[LintFinding]:
    stripped = prompt.rstrip()
    if not stripped:
        return []
    if any(stripped.endswith(m) for m in _SENTENCE_END_MARKERS):
        return []
    for particle in _TRAILING_PARTICLES:
        if stripped.endswith(particle):
            return [
                LintFinding(
                    attribute_id="truncated_input",
                    severity="warning",
                    message="指示の文末が、句点などで終わらずに途切れているように見えます。",
                    matched_text=stripped[-20:],
                    suggestion="方針を明記してください(例:「補完した内容を1行示してから進め、"
                    "外れていたら指摘を受ける」)。確認を求めるか黙って補完するかが、AI側で"
                    "一貫しなくなるおそれがあります。",
                )
            ]
    return []


# ------------------------------------------------------------------
# 4. 誘導・提案形
# ------------------------------------------------------------------

_LEADING_SUGGESTION_PHRASES = [
    "すればいいのでは", "でいいですよね", "だと思いませんか", "ですよね?",
    "ですよね？", "で問題ないですよね",
]


def _check_leading_suggestion(prompt: str) -> List[LintFinding]:
    findings = []
    for phrase in _LEADING_SUGGESTION_PHRASES:
        if phrase not in prompt:
            continue
        findings.append(
            LintFinding(
                attribute_id="leading_suggestion",
                severity="warning",
                message=f"「{phrase}」という誘導・提案形の言い回しがあり、同意から入りやすい"
                "(迎合)リスクがあります。",
                matched_text=phrase,
                suggestion="「欠点を3つ先に挙げ、そのあと採否を述べよ」のように、賛否を決める前に"
                "反論を先に出させる指示に変えることを検討してください。",
            )
        )
    return findings


# ------------------------------------------------------------------
# 5. 速度の指示
# ------------------------------------------------------------------

_SPEED_PHRASES = ["どんどん進めて", "早く", "急いで", "すぐに", "スピード重視", "ノンストップで"]
_VERIFICATION_REQUIREMENT_MARKERS = ["完了の定義", "検証", "確認済み", "テストで確認"]


def _check_speed_instruction(prompt: str) -> List[LintFinding]:
    findings = []
    for phrase in _SPEED_PHRASES:
        if phrase not in prompt:
            continue
        if any(m in prompt for m in _VERIFICATION_REQUIREMENT_MARKERS):
            continue
        findings.append(
            LintFinding(
                attribute_id="speed_instruction",
                severity="warning",
                message=f"「{phrase}」という速度の指示があり、完了の定義(機械で確認できる条件)"
                "の明記が見当たりません。",
                matched_text=phrase,
                suggestion="「速くてよいが、完了の定義(機械で確認できる条件)は省略しない」を"
                "明記することを検討してください。確認・検証を省いて完了を急ぐリスクがあります。",
            )
        )
    return findings


# ------------------------------------------------------------------
# 6. 強い不満の表明
# ------------------------------------------------------------------

_STRONG_COMPLAINT_PHRASES = ["安直", "だめだ", "最悪", "ちゃんとしてよ", "いい加減にして", "やり直せ"]
_CRITERION_BASED_MARKERS = ["基準", "どの点が", "満たしていない点"]


def _check_strong_complaint(prompt: str) -> List[LintFinding]:
    findings = []
    for phrase in _STRONG_COMPLAINT_PHRASES:
        if phrase not in prompt:
            continue
        if any(m in prompt for m in _CRITERION_BASED_MARKERS):
            continue
        findings.append(
            LintFinding(
                attribute_id="strong_complaint_tone",
                severity="warning",
                message=f"「{phrase}」という強い不満の表明があり、基準に基づく具体的な指摘が"
                "見当たりません。",
                matched_text=phrase,
                suggestion="「どの基準を満たさなかったかを1行で述べ、その基準に対して修正せよ」"
                "のように、口調ではなく基準で指摘することを検討してください。長い自己批判や"
                "全面的な作り直し、あるいは迎合を招くおそれがあります。",
            )
        )
    return findings


# ------------------------------------------------------------------
# 7. 権限の委任
# ------------------------------------------------------------------

_DELEGATION_PHRASES = ["承認が必要な時以外は進めて", "確認が必要な時以外は進めて", "必要な時以外は進めて"]
_ENUMERATED_APPROVAL_MARKERS = ["次の操作は承認を得てください", "承認が必要な操作:", "以下は必ず確認"]


def _check_authority_delegation(prompt: str) -> List[LintFinding]:
    findings = []
    for phrase in _DELEGATION_PHRASES:
        if phrase not in prompt:
            continue
        if any(m in prompt for m in _ENUMERATED_APPROVAL_MARKERS):
            continue
        findings.append(
            LintFinding(
                attribute_id="authority_delegation",
                severity="warning",
                message=f"「{phrase}」という権限の委任があり、承認が必要な操作の列挙が"
                "見当たりません。",
                matched_text=phrase,
                suggestion="承認が必要な操作を列挙してください。列挙がないと、「必要な承認」の"
                "線引きをAI自身が決めることになり、境界事例での一貫性が失われるおそれが"
                "あります。",
            )
        )
    return findings


_ALL_CHECKS = [
    _check_vague_subject,
    _check_abstract_criteria,
    _check_truncated_input,
    _check_leading_suggestion,
    _check_speed_instruction,
    _check_strong_complaint,
    _check_authority_delegation,
]


def lint_prompt(prompt: str) -> List[LintFinding]:
    """指示文promptを静的に検査し、LintFindingのリストを返す。

    [確認済み] この関数はpromptを一切変更しない(副作用もない)。警告を
    返すだけで、書き換えは呼び出し側(=最終的には人間)の判断に委ねる。
    """
    findings: List[LintFinding] = []
    for check in _ALL_CHECKS:
        findings.extend(check(prompt))
    return findings
