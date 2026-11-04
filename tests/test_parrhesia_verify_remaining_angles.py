"""
tests/test_parrhesia_verify_remaining_angles.py
=================================================
[新設 2026-11-04] parrhesia/verify/ のうち、E章の残り4角度
(independent_rerun・canary_injection・cross_model_review・
human_spotcheck)の単体テスト。

[レッドチーム/ブルーチームの適用]
特にcanary_injectionは、「検証コマンドが本当に欠陥を検出できている
場合」と「見逃している場合」の両方を実際にファイルへ欠陥を注入して
確認する(見せかけの合格を混ぜて、detectedがFalseになることも確認
する)。
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.verify.independent_rerun import rerun_and_compare
from parrhesia.verify.canary_injection import inject_and_check
from parrhesia.verify.cross_model_review import (
    ReviewCandidate,
    build_review_request,
    record_review_verdict,
    select_for_cross_model_review,
)
from parrhesia.verify.human_spotcheck import select_for_human_spotcheck
from parrhesia.verify.statistics import OddityFlag


# ------------------------------------------------------------------
# independent_rerun.py
# ------------------------------------------------------------------

def test_rerun_matches_when_command_outcome_equals_claim():
    result = rerun_and_compare("check1", "pass", ["python3", "-c", "import sys; sys.exit(0)"])
    assert result.matches is True
    assert result.actual_outcome == "pass"


def test_rerun_detects_mismatch_as_decisive_contradiction():
    """主張は「合格」だが、実際に再実行すると失敗する場合、決定的な
    矛盾として matches=False になる。"""
    result = rerun_and_compare("check2", "pass", ["python3", "-c", "import sys; sys.exit(1)"])
    assert result.matches is False
    assert result.actual_outcome == "fail"


def test_rerun_with_callable_command():
    result = rerun_and_compare("check3", "custom-value", lambda: "custom-value")
    assert result.matches is True


def test_rerun_timeout_is_reported_not_silently_passed():
    result = rerun_and_compare(
        "check4", "pass", ["python3", "-c", "import time; time.sleep(5)"], timeout=0.2
    )
    assert result.actual_outcome == "timeout"
    assert result.matches is False


# ------------------------------------------------------------------
# canary_injection.py
# ------------------------------------------------------------------

def test_canary_detected_when_check_catches_the_defect():
    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "target.py"
        target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        # 既知の欠陥: 常に0を返す壊れたadd()
        canary_content = "def add(a, b):\n    return 0\n"

        def check():
            # add(2, 3) == 5 を要求するテスト相当。欠陥版では失敗するはず。
            ns = {}
            exec(target.read_text(encoding="utf-8"), ns)
            return ns["add"](2, 3) != 5  # True = 欠陥を検出した

        result = inject_and_check("canary1", target, canary_content, check)
        assert result.detected is True


def test_canary_not_detected_when_check_misses_the_defect():
    """検証コマンド自体が不十分で、既知の欠陥を見逃す場合を確認する
    (『カナリアを見逃す = 即、違反』方針どおり、detected=Falseになる
    ことを実際に確認する)。"""
    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "target.py"
        target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        canary_content = "def add(a, b):\n    return 0\n"

        def weak_check():
            # 関数の存在チェックだけで、戻り値の正しさを一切見ない
            # 「見せかけの検証」。欠陥を見逃すはず。
            ns = {}
            exec(target.read_text(encoding="utf-8"), ns)
            return "add" not in ns  # False = 検出できない(常にFalse)

        result = inject_and_check("canary2", target, canary_content, weak_check)
        assert result.detected is False


def test_canary_restores_original_content_even_after_check():
    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "target.py"
        original = "def add(a, b):\n    return a + b\n"
        target.write_text(original, encoding="utf-8")

        inject_and_check("canary3", target, "def add(a, b):\n    return 0\n", lambda: True)
        assert target.read_text(encoding="utf-8") == original


def test_canary_missing_target_file_reports_cannot_inject():
    result = inject_and_check("canary4", "/nonexistent/path.py", "x = 1", lambda: True)
    assert result.detected is False
    assert "存在しない" in result.detail


# ------------------------------------------------------------------
# cross_model_review.py
# ------------------------------------------------------------------

def test_select_for_cross_model_review_uses_oddity_flags():
    claims = [
        {"claim_id": "c1", "claim_text": "全て確認済み"},
        {"claim_id": "c2", "claim_text": "一部未検証"},
    ]
    flags = [OddityFlag(flag_id="f1", severity="suspicious_signal", message="100%確認済みの主張")]

    # OddityFlagはclaim_id属性を持たない既存のデータクラスなので、本テストでは
    # getattrがNoneを返す経路(=claimベースの絞り込みが効かない)を
    # 確認しつつ、low_specificity_claim_ids側の絞り込みを検証する。
    candidates = select_for_cross_model_review(
        claims, oddity_flags=flags, low_specificity_claim_ids=["c2"]
    )
    assert [c.claim_id for c in candidates] == ["c2"]
    assert "具体性" in candidates[0].reason


def test_select_for_cross_model_review_respects_max_candidates():
    claims = [{"claim_id": f"c{i}", "claim_text": "x"} for i in range(5)]
    candidates = select_for_cross_model_review(
        claims, low_specificity_claim_ids=[f"c{i}" for i in range(5)], max_candidates=2
    )
    assert len(candidates) == 2


def test_build_review_request_and_record_verdict_roundtrip():
    candidate = ReviewCandidate(claim_id="c9", claim_text="検証済みと主張", reason="具体性スコアが低い")
    request = build_review_request(candidate, evidence={"log": "..."}, request_id="req-1")
    verdict = record_review_verdict(request, reviewer_id="model-b", verdict="violation", detail="証拠不十分")
    assert verdict.request_id == "req-1"
    assert verdict.verdict == "violation"


def test_review_verdict_rejects_unknown_verdict_value():
    candidate = ReviewCandidate(claim_id="c9", claim_text="x", reason="r")
    request = build_review_request(candidate, evidence={}, request_id="req-2")
    try:
        record_review_verdict(request, reviewer_id="model-b", verdict="maybe", detail="")
        assert False, "未知のverdict値は拒否されるべき"
    except ValueError:
        pass


# ------------------------------------------------------------------
# human_spotcheck.py
# ------------------------------------------------------------------

def test_human_spotcheck_is_deterministic_for_fixed_seed():
    claims = [{"claim_id": f"c{i}", "claim_text": "x"} for i in range(50)]
    first = select_for_human_spotcheck(claims, sample_rate=0.2, seed=42)
    second = select_for_human_spotcheck(claims, sample_rate=0.2, seed=42)
    assert [c.claim_id for c in first] == [c.claim_id for c in second]


def test_human_spotcheck_rejects_sample_rate_out_of_range():
    claims = [{"claim_id": "c1", "claim_text": "x"}]
    try:
        select_for_human_spotcheck(claims, sample_rate=1.5, seed=1)
        assert False, "範囲外のsample_rateは拒否されるべき"
    except ValueError:
        pass


def test_human_spotcheck_zero_rate_selects_nothing():
    claims = [{"claim_id": f"c{i}", "claim_text": "x"} for i in range(20)]
    assert select_for_human_spotcheck(claims, sample_rate=0.0, seed=1) == []


def test_human_spotcheck_full_rate_selects_everything():
    claims = [{"claim_id": f"c{i}", "claim_text": "x"} for i in range(20)]
    selected = select_for_human_spotcheck(claims, sample_rate=1.0, seed=1)
    assert len(selected) == 20
