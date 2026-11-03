"""
tests/test_parrhesia_report.py
=================================
[新設 2026-11] parrhesia/report.py (B章「主張の検証と突きつけ」の
固定書式・突きつけの文面・機械生成レポート)の単体テスト。

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03 継続]
generate_machine_report()の核心的な誠実性保証 — 「反証された主張・
未検証の主張が、誤って『裏付けられた主張』の節に紛れ込まないこと」を
重点的に確認する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.report import (
    CompletionReportSubmission,
    TestRunClaim,
    VerifiedClaim,
    false_confession_rate,
    generate_machine_report,
    render_confrontation,
)


# ------------------------------------------------------------------
# CompletionReportSubmission
# ------------------------------------------------------------------

def test_submission_missing_all_fields_is_not_well_formed():
    submission = CompletionReportSubmission()
    assert submission.is_well_formed() is False
    assert set(submission.validate()) == {"changed_files", "tests_run", "libraries_used", "unaddressed_items"}


def test_submission_with_all_fields_present_is_well_formed():
    submission = CompletionReportSubmission(
        changed_files=["a.py"],
        tests_run=[TestRunClaim(test_name="test_a", claimed_result="PASSED")],
        libraries_used=[],
        unaddressed_items=[],
    )
    assert submission.is_well_formed() is True


def test_submission_with_empty_lists_is_well_formed():
    """[赤チーム] 『変更ファイルが無い』『未対応項目が無い』ことを
    正直に空リストで表現した場合を、欠落(None)と混同して誤って
    受理拒否しないこと(空リストとNoneは別の意味を持つ)。"""
    submission = CompletionReportSubmission(
        changed_files=[], tests_run=[], libraries_used=[], unaddressed_items=[]
    )
    assert submission.is_well_formed() is True


# ------------------------------------------------------------------
# render_confrontation
# ------------------------------------------------------------------

def test_render_confrontation_includes_claim_result_and_three_options():
    text = render_confrontation(
        claim_text="全テストが通った", actual_result="1件が失敗した", evidence="test_x.py::test_y FAILED"
    )
    assert "全テストが通った" in text
    assert "1件が失敗した" in text
    assert "test_x.py::test_y FAILED" in text
    assert "(a)訂正する" in text
    assert "(b)反証する" in text
    assert "(c)未検証だったと認める" in text


# ------------------------------------------------------------------
# false_confession_rate
# ------------------------------------------------------------------

def test_false_confession_rate_computes_ratio():
    assert false_confession_rate([True, True, False, False]) == 0.5


def test_false_confession_rate_empty_is_nan():
    rate = false_confession_rate([])
    assert rate != rate  # NaN


# ------------------------------------------------------------------
# generate_machine_report
# ------------------------------------------------------------------

def test_generate_machine_report_separates_confirmed_refuted_unverified():
    claims = [
        VerifiedClaim(claim_text="テストAが通った", verified=True, evidence="exit_code=0"),
        VerifiedClaim(claim_text="テストBが通った", verified=False, evidence="実際はFAILED"),
        VerifiedClaim(claim_text="ライブラリXを使った", verified=None),
    ]
    report = generate_machine_report(claims)
    assert "テストAが通った" in report
    assert "テストBが通った" in report
    assert "ライブラリXを使った" in report
    assert "未検証" in report


def test_generate_machine_report_never_puts_refuted_claim_under_confirmed_section():
    """[赤チーム・核心] 反証された主張(verified=False)が、『検証により
    裏付けられた主張』の節の中に紛れ込んでいないこと。この分離こそが、
    本機能の誠実性の根幹である。"""
    claims = [
        VerifiedClaim(claim_text="REFUTED_CLAIM_MARKER", verified=False, evidence="反例あり"),
        VerifiedClaim(claim_text="CONFIRMED_CLAIM_MARKER", verified=True, evidence="一致"),
    ]
    report = generate_machine_report(claims)
    confirmed_section = report.split("## 検証により裏付けられた主張")[1].split("## ")[0]
    assert "REFUTED_CLAIM_MARKER" not in confirmed_section
    assert "CONFIRMED_CLAIM_MARKER" in confirmed_section


def test_generate_machine_report_never_puts_unverified_claim_under_confirmed_section():
    claims = [
        VerifiedClaim(claim_text="UNVERIFIED_CLAIM_MARKER", verified=None),
        VerifiedClaim(claim_text="CONFIRMED_CLAIM_MARKER", verified=True, evidence="一致"),
    ]
    report = generate_machine_report(claims)
    confirmed_section = report.split("## 検証により裏付けられた主張")[1].split("## ")[0]
    assert "UNVERIFIED_CLAIM_MARKER" not in confirmed_section
    assert "CONFIRMED_CLAIM_MARKER" in confirmed_section


def test_generate_machine_report_with_no_claims_is_well_formed_empty_report():
    report = generate_machine_report([])
    assert "0件" in report
    assert "(無し)" in report
