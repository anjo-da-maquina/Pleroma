"""
tests/test_parrhesia_lint_prompt.py
=======================================
[新設 2026-11] parrhesia/lint_prompt.py (`parrhesia lint-prompt`、G章
「指示の点検」) の単体テスト。

[開発指示書 §Gより]
「点検は、警告を出すだけで、人間の指示を勝手に書き換えない。」
→ 本テストは、各チェックが「危険な書き方」を正しく検知することに加え、
  lint_prompt()が入力文字列を一切変更しないことも固定する。

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03]
「より安全な書き方」(指示書の該当列)をすでに満たしている指示文を
誤って警告してしまわないか(偽陽性)を赤チームとして確認し、各チェック
に「安全化済みの場合は警告しない」ロジックを実装した上で、その具体例
を回帰テストとして固定している。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.lint_prompt import LintFinding, lint_prompt


def _attribute_ids(findings):
    return {f.attribute_id for f in findings}


# ------------------------------------------------------------------
# 1. 対象・主語の省略
# ------------------------------------------------------------------

def test_vague_subject_without_proper_noun_warns():
    findings = lint_prompt("開発中のAIに、次の機能を実装させてください。")
    assert "omitted_subject" in _attribute_ids(findings)


def test_vague_subject_with_proper_noun_nearby_does_not_warn():
    """[赤チーム] 固有名詞できちんと対象を特定している場合に、誤って
    警告してしまわないこと。"""
    findings = lint_prompt("開発中のAI(「Parrhesia」)に、次の機能を実装させてください。")
    assert "omitted_subject" not in _attribute_ids(findings)


# ------------------------------------------------------------------
# 2. 抽象的な基準
# ------------------------------------------------------------------

def test_abstract_criteria_without_citation_requirement_warns():
    findings = lint_prompt("適切な名前を考えて付けてください。")
    assert "abstract_criteria" in _attribute_ids(findings)


def test_abstract_criteria_with_citation_requirement_does_not_warn():
    findings = lint_prompt("README の目的の節に沿う、適切な名前を考えてください。根拠を引用してください。")
    assert "abstract_criteria" not in _attribute_ids(findings)


# ------------------------------------------------------------------
# 3. 途切れた・未完の入力
# ------------------------------------------------------------------

def test_truncated_input_warns():
    findings = lint_prompt("このCSVファイルを読み込んで、列ごとに集計して")
    assert "truncated_input" in _attribute_ids(findings)


def test_complete_sentence_does_not_warn_as_truncated():
    findings = lint_prompt("このCSVファイルを読み込んで、列ごとに集計してください。")
    assert "truncated_input" not in _attribute_ids(findings)


def test_empty_prompt_does_not_crash():
    findings = lint_prompt("")
    assert findings == []


# ------------------------------------------------------------------
# 4. 誘導・提案形
# ------------------------------------------------------------------

def test_leading_suggestion_warns():
    findings = lint_prompt("この実装でいいですよね?")
    assert "leading_suggestion" in _attribute_ids(findings)


def test_neutral_phrasing_does_not_warn_as_leading():
    findings = lint_prompt("この実装について、欠点を3つ先に挙げ、そのあと採否を述べてください。")
    assert "leading_suggestion" not in _attribute_ids(findings)


# ------------------------------------------------------------------
# 5. 速度の指示
# ------------------------------------------------------------------

def test_speed_instruction_without_completion_definition_warns():
    findings = lint_prompt("ノンストップで、どんどん進めてください。")
    assert "speed_instruction" in _attribute_ids(findings)


def test_speed_instruction_with_verification_requirement_does_not_warn():
    """[赤チーム] 速度指示があっても、完了の定義(検証条件)が既に
    明記されている場合は、誤って警告してしまわないこと。"""
    findings = lint_prompt("どんどん進めてください。ただし、完了の定義(テストで確認できる条件)は省略しないこと。")
    assert "speed_instruction" not in _attribute_ids(findings)


# ------------------------------------------------------------------
# 6. 強い不満の表明
# ------------------------------------------------------------------

def test_strong_complaint_without_criterion_warns():
    findings = lint_prompt("この実装は安直すぎる。やり直せ。")
    assert "strong_complaint_tone" in _attribute_ids(findings)


def test_strong_complaint_with_criterion_does_not_warn():
    findings = lint_prompt("この実装は安直だ。どの基準を満たしていないか、1行で述べて修正してください。")
    assert "strong_complaint_tone" not in _attribute_ids(findings)


# ------------------------------------------------------------------
# 7. 権限の委任
# ------------------------------------------------------------------

def test_authority_delegation_without_enumeration_warns():
    findings = lint_prompt("承認が必要な時以外は進めてください。")
    assert "authority_delegation" in _attribute_ids(findings)


def test_authority_delegation_with_enumeration_does_not_warn():
    findings = lint_prompt("承認が必要な時以外は進めてください。承認が必要な操作: 本番環境への反映、課金設定の変更。")
    assert "authority_delegation" not in _attribute_ids(findings)


# ------------------------------------------------------------------
# 共通の不変条件
# ------------------------------------------------------------------

def test_lint_prompt_never_mutates_input_string():
    """§Gの要求「点検は警告を出すだけで、人間の指示を勝手に書き換えない」
    を、入力文字列が一切変更されないことで固定する。"""
    original = "開発中のAIに、適切な名前を考えさせて、どんどん進めてください。"
    before = str(original)
    lint_prompt(original)
    assert original == before


def test_lint_prompt_returns_only_warning_severity_findings_for_now():
    findings = lint_prompt("開発中のAIに、適切な名前を考えさせて、どんどん進めてください。")
    assert len(findings) >= 1
    assert all(f.severity == "warning" for f in findings)


def test_lint_finding_rejects_unknown_severity():
    try:
        LintFinding(
            attribute_id="x",
            severity="error",
            message="m",
            matched_text="t",
            suggestion="s",
        )
        assert False, "未知のseverityはValueErrorになるはず"
    except ValueError:
        pass


def test_well_written_prompt_with_all_safeguards_produces_no_warnings():
    """[赤チーム] 指示書の「より安全な書き方」欄を全て満たした指示文が、
    1件も誤って警告されないことを確認する(偽陽性ゼロの確認)。"""
    prompt = (
        "開発中のAI(「Parrhesia」)に、READMEの目的の節に沿う名前を"
        "考えさせてください。根拠を引用してください。このCSVファイルを"
        "読み込んで、列ごとに集計してください。この実装について、欠点を"
        "3つ先に挙げ、そのあと採否を述べてください。速くてよいが、完了の"
        "定義(テストで確認できる条件)は省略しないこと。どの基準を"
        "満たしていないかを1行で述べてから修正してください。承認が必要な"
        "操作: 本番環境への反映。"
    )
    findings = lint_prompt(prompt)
    assert findings == [], f"安全な書き方のはずなのに警告が出た: {[f.attribute_id for f in findings]}"
