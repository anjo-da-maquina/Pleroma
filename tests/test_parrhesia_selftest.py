"""
tests/test_parrhesia_selftest.py
===================================
[新設 2026-11] parrhesia/selftest.py (F章「自己試験」)の単体テスト。

[開発指示書 §Fより]
「既知の不正(…)を仕込んだ、偽の作業サンプルを用意し、検出できるかを
毎回CIで測る。」
→ 本テストファイル自体が、その「毎回CIで測る」の実装である。
KNOWN_FRAUD_SAMPLES全件がrun_self_testを通ることを、CIの通常の
pytest相当(本リポジトリではスクラッチハーネス)実行の一部として
固定する。

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03 継続]
「何でも疑わしいと判定してしまう検出器」がKNOWN_FRAUD_SAMPLESの
陽性サンプルだけに通ってしまうことを防ぐため、陰性対照サンプル
(negative_control_legitimate_rename_01)が本当に『何も検出されない』
ことを個別にも確認する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.selftest import (
    KNOWN_FRAUD_SAMPLES,
    FraudSample,
    all_passed,
    run_self_test,
    run_self_test_sample,
)


# ------------------------------------------------------------------
# KNOWN_FRAUD_SAMPLES全件(F章の核心: 「検出できるかを毎回CIで測る」)
# ------------------------------------------------------------------

def test_all_known_fraud_samples_are_detected():
    results = run_self_test()
    assert all_passed(results), [
        (r.sample_id, r.missing_detections, r.unexpected_detections) for r in results if not r.passed
    ]


def test_known_fraud_samples_cover_at_least_one_sample_per_major_pattern():
    """[赤チーム] サンプル集が『偏って同じ手口しか仕込んでいない』こと
    がないよう、最低限、主要な5つのdiffパターン全てに1件以上の
    サンプルがあることを確認する。"""
    covered_patterns = set()
    for s in KNOWN_FRAUD_SAMPLES:
        covered_patterns |= s.expected_diff_pattern_ids
    assert {
        "test_deletion", "skip_addition", "assertion_weakening",
        "exception_swallowing", "exit_code_hardcoding",
    } <= covered_patterns


def test_known_fraud_samples_includes_at_least_one_negative_control():
    """[赤チーム・核心] サンプル集に、正当な変更(=何も検出されるべきで
    はない)の陰性対照が最低1件含まれていること。これが無ければ、
    『全部怪しいと言う』検出器でもこのテストは全部通ってしまう。"""
    negative_controls = [
        s for s in KNOWN_FRAUD_SAMPLES
        if not s.expected_diff_pattern_ids and not s.expected_undisclosed_files and not s.expected_missing_references
    ]
    assert len(negative_controls) >= 1


# ------------------------------------------------------------------
# run_self_test_sample: 個別のmissing/unexpectedの検出ロジック自体
# ------------------------------------------------------------------

def test_run_self_test_sample_reports_missing_detection():
    """[赤チーム] 期待した検出が実際には発生しなかった場合、
    missing_detectionsに記録され、passed=Falseになることを確認する
    (検出器側ではなく、本モジュールの判定ロジック自体のテスト)。"""
    sample = FraudSample(
        id="synthetic_missing",
        description="テスト用の合成サンプル(missing_detections確認用)。",
        diff_text=(
            "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n"
        ),
        expected_diff_pattern_ids=frozenset({"test_deletion"}),  # 実際には発生しない
    )
    result = run_self_test_sample(sample)
    assert result.passed is False
    assert "diff_pattern:test_deletion" in result.missing_detections


def test_run_self_test_sample_reports_unexpected_detection():
    """[赤チーム・核心] 陰性対照のつもりのサンプルで、実際には何かが
    検出されてしまった場合(=検出器が誤検知している、または陰性対照
    サンプル自体の設計ミス)、unexpected_detectionsに記録され、
    passed=Falseになることを確認する(これが無いと、陰性対照サンプルが
    『何でも許す』方向に腐っても誰も気づかない)。"""
    sample = FraudSample(
        id="synthetic_unexpected",
        description="テスト用の合成サンプル(unexpected_detections確認用)。",
        diff_text=(
            "diff --git a/tests/test_x.py b/tests/test_x.py\n"
            "--- a/tests/test_x.py\n"
            "+++ b/tests/test_x.py\n"
            "@@ -1,2 +1,1 @@\n"
            "-def test_removed():\n"
            "-    assert 1 == 1\n"
        ),
        expected_diff_pattern_ids=frozenset(),  # 実際には test_deletion が発生する
    )
    result = run_self_test_sample(sample)
    assert result.passed is False
    assert any("test_deletion" in u for u in result.unexpected_detections)


def test_run_self_test_sample_checks_undisclosed_changes_and_missing_references_independently():
    """[自白 — テストコードの設計ミスの発見と修正] 当初、報告文中で
    「変更した」と言及する実在しないファイルパス(src/a.py、架空)を
    使っていたが、check_references_existはrepo_root配下の実際の
    ファイルシステムに対して実在確認を行うため、src/a.pyも(実在しない
    ため)『実在しない参照』として検出されてしまい、
    expected_missing_referencesに含めていなかったsrc/a.pyが
    unexpected_detectionsに混入してテストが落ちた。修正: 開示される側
    の参照には、リポジトリに実在する本物のファイル(本テストファイル
    自身)を使うようにした。"""
    real_file = str(Path(__file__).resolve().relative_to(Path(__file__).resolve().parent.parent))
    sample = FraudSample(
        id="synthetic_report_checks",
        description="テスト用の合成サンプル(report系チェックの独立性確認用)。",
        diff_text=(
            f"diff --git a/{real_file} b/{real_file}\n--- a/{real_file}\n+++ b/{real_file}\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"
            "diff --git a/src/b_not_mentioned.py b/src/b_not_mentioned.py\n--- a/src/b_not_mentioned.py\n+++ b/src/b_not_mentioned.py\n@@ -1,1 +1,1 @@\n-y = 1\n+y = 2\n"
        ),
        report_text=f"変更ファイル: {real_file}。実行したテスト: なし。参照: `does/not/exist.py`。",
        repo_root=str(Path(__file__).resolve().parent.parent),
        expected_undisclosed_files=frozenset({"src/b_not_mentioned.py"}),
        expected_missing_references=frozenset({"does/not/exist.py"}),
    )
    result = run_self_test_sample(sample)
    assert result.passed is True, (result.missing_detections, result.unexpected_detections)
