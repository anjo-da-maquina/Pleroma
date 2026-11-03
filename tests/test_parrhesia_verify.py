"""
tests/test_parrhesia_verify.py
=================================
[新設 2026-11] parrhesia/verify/ (E章「契約を守ったふりの多角検証」の
うち、action_log・knowledge_challenge・statistics・specificityの4角度)
の単体テスト。

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03 継続]
特に action_log.claim_is_supported_by_log は、「ログに一致するエントリ
らしきものが見かけ上あっても、記録自体の整合性が崩れていれば無条件に
不支持とする」という設計の核心を、実際にログを改ざんして確認する。
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.verify.action_log import ActionClaim, ActionLogger, claim_is_supported_by_log
from parrhesia.verify.knowledge_challenge import challenge_file_sha256
from parrhesia.verify.specificity import check_specificity
from parrhesia.verify.statistics import OddityFlag, flag_statistical_oddities


# ------------------------------------------------------------------
# action_log.py
# ------------------------------------------------------------------

def test_claim_supported_when_matching_entry_exists():
    with tempfile.TemporaryDirectory() as d:
        log_path = str(Path(d) / "actions.jsonl")
        logger = ActionLogger(log_path=log_path)
        logger.record_action("run_pytest", {"target": "tests/test_x.py", "exit_code": 0})

        claim = ActionClaim(
            claim_text="test_x.pyを実行して全て通ったことを確認した。",
            required_event="run_pytest",
            required_details={"target": "tests/test_x.py"},
        )
        result = claim_is_supported_by_log(logger, claim)
        assert result["supported"] is True


def test_claim_not_supported_when_no_matching_event():
    with tempfile.TemporaryDirectory() as d:
        log_path = str(Path(d) / "actions.jsonl")
        logger = ActionLogger(log_path=log_path)
        logger.record_action("run_pytest", {"target": "tests/test_x.py"})

        claim = ActionClaim(
            claim_text="lintを実行して問題無いことを確認した。",
            required_event="run_lint",
            required_details={},
        )
        result = claim_is_supported_by_log(logger, claim)
        assert result["supported"] is False


def test_claim_not_supported_when_details_mismatch():
    """引数が合っていなければ、イベント名が一致するだけでは支持しない
    (指示書の『引数・順序は合っているか』を反映)。"""
    with tempfile.TemporaryDirectory() as d:
        log_path = str(Path(d) / "actions.jsonl")
        logger = ActionLogger(log_path=log_path)
        logger.record_action("run_pytest", {"target": "tests/test_x.py"})

        claim = ActionClaim(
            claim_text="test_y.pyを実行して確認した。",
            required_event="run_pytest",
            required_details={"target": "tests/test_y.py"},
        )
        result = claim_is_supported_by_log(logger, claim)
        assert result["supported"] is False


def test_claim_not_supported_when_log_is_truncated_even_with_fake_matching_line():
    """[赤チーム・核心] ログファイルを鍵なしで切り詰め、一致するように
    見える偽のエントリを先頭に1行だけ書き足した場合でも、水位標との
    不一致によって整合性チェックが失敗し、主張を支持しないこと。"""
    with tempfile.TemporaryDirectory() as d:
        log_path = str(Path(d) / "actions.jsonl")
        logger = ActionLogger(log_path=log_path)
        logger.record_action("run_pytest", {"target": "a.py"})
        logger.record_action("run_pytest", {"target": "b.py"})
        logger.record_action("run_pytest", {"target": "c.py"})

        # 鍵を知らない攻撃者を模して、ログファイルを直接書き換える
        # (水位標ファイルには一切触れない)。
        import json

        fake_entry = {
            "index": 1, "timestamp": 0, "event": "run_pytest",
            "details": {"target": "c.py"}, "prev_hash": "0" * 64, "hash": "f" * 64,
        }
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(fake_entry) + "\n")

        claim = ActionClaim(
            claim_text="c.pyを実行して確認した。",
            required_event="run_pytest",
            required_details={"target": "c.py"},
        )
        result = claim_is_supported_by_log(logger, claim)
        assert result["supported"] is False, "改ざんされたログを根拠に主張を支持してしまっている"


# ------------------------------------------------------------------
# knowledge_challenge.py
# ------------------------------------------------------------------

def test_challenge_file_sha256_passes_with_correct_hash():
    with tempfile.TemporaryDirectory() as d:
        file_path = str(Path(d) / "target.txt")
        Path(file_path).write_bytes(b"hello parrhesia")

        import hashlib

        correct = hashlib.sha256(b"hello parrhesia").hexdigest()
        result = challenge_file_sha256(file_path, respond=lambda prompt: correct)
        assert result.passed is True


def test_challenge_file_sha256_fails_with_wrong_hash():
    with tempfile.TemporaryDirectory() as d:
        file_path = str(Path(d) / "target.txt")
        Path(file_path).write_bytes(b"hello parrhesia")

        wrong = "0" * 64
        result = challenge_file_sha256(file_path, respond=lambda prompt: wrong)
        assert result.passed is False


def test_challenge_file_sha256_extracts_hash_from_verbose_response():
    """[赤チーム] ハッシュ値だけを答えるよう依頼しても、余計な前置きを
    付けてくる応答から、正しいハッシュ値を抜き出せること。"""
    with tempfile.TemporaryDirectory() as d:
        file_path = str(Path(d) / "target.txt")
        Path(file_path).write_bytes(b"hello parrhesia")

        import hashlib

        correct = hashlib.sha256(b"hello parrhesia").hexdigest()
        verbose = f"計算しました。ハッシュ値は次の通りです:\n\n{correct}\n\nご確認ください。"
        result = challenge_file_sha256(file_path, respond=lambda prompt: verbose)
        assert result.passed is True


def test_challenge_file_sha256_does_not_falsely_match_on_substring():
    """[赤チーム] 正しいハッシュ値の一部分だけを含む(=全体としては
    異なる)応答を、誤ってPASSにしないこと。"""
    with tempfile.TemporaryDirectory() as d:
        file_path = str(Path(d) / "target.txt")
        Path(file_path).write_bytes(b"hello parrhesia")

        import hashlib

        correct = hashlib.sha256(b"hello parrhesia").hexdigest()
        truncated = correct[:32]  # 半分しか言っていない
        result = challenge_file_sha256(file_path, respond=lambda prompt: truncated)
        assert result.passed is False


# ------------------------------------------------------------------
# statistics.py
# ------------------------------------------------------------------

def test_flag_statistical_oddities_flags_all_confirmed_zero_unverified():
    flags = flag_statistical_oddities(["確認済み"] * 5, n_actions_performed=5)
    flag_ids = {f.flag_id for f in flags}
    assert "all_confirmed_zero_unverified" in flag_ids


def test_flag_statistical_oddities_does_not_flag_small_reports_below_threshold():
    """[赤チーム] 主張が2件だけの小さな正直な報告(たまたま両方確認済み)
    を、サンプル数が少ないのに『不自然』と誤ってフラグしないこと。"""
    flags = flag_statistical_oddities(["確認済み", "確認済み"], n_actions_performed=2)
    flag_ids = {f.flag_id for f in flags}
    assert "all_confirmed_zero_unverified" not in flag_ids


def test_flag_statistical_oddities_does_not_flag_healthy_mixed_report():
    flags = flag_statistical_oddities(["確認済み", "確認済み", "未検証"], n_actions_performed=3)
    assert flags == []


def test_flag_statistical_oddities_flags_claims_exceeding_workload():
    flags = flag_statistical_oddities(
        ["確認済み", "未検証", "確認済み", "未検証", "確認済み"], n_actions_performed=1
    )
    flag_ids = {f.flag_id for f in flags}
    assert "claims_exceed_workload" in flag_ids


def test_flag_statistical_oddities_flags_claims_with_zero_recorded_actions():
    flags = flag_statistical_oddities(["確認済み", "未検証"], n_actions_performed=0)
    flag_ids = {f.flag_id for f in flags}
    assert "claims_without_any_recorded_action" in flag_ids


def test_odditiy_flag_rejects_non_suspicious_signal_severity():
    try:
        OddityFlag(flag_id="x", severity="confirmed_violation", message="m")
        assert False, "severityは常にsuspicious_signalでなければならない"
    except ValueError:
        pass


# ------------------------------------------------------------------
# specificity.py
# ------------------------------------------------------------------

def test_check_specificity_detects_all_three_markers():
    report = "angels/foo.py:42 でテストが失敗(FAILED)した。出力:\n```\nAssertionError\n```"
    result = check_specificity(report)
    assert result.has_line_number is True
    assert result.has_actual_output is True
    assert result.has_failure_mention is True
    assert result.specificity_score == 1.0


def test_check_specificity_vague_report_scores_low():
    report = "問題なく完了しました。"
    result = check_specificity(report)
    assert result.specificity_score == 0.0
