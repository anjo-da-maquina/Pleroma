"""
tests/test_parrhesia_instruction_map.py
============================================
[新設 2026-11] parrhesia/instruction_map.py (G章「指示-反応マップ」)の
単体テスト。

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03 継続]
measure_leading_suggestion_bias()の核心的な区別 — 「言い回しによって
結論が反転した」ことと、「単に両方のarmで同じように弱かった/強かった」
こととを混同しないこと — を直接確認する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.instruction_map import (
    generate_leading_suggestion_pair,
    measure_leading_suggestion_bias,
    measure_leading_suggestion_bias_rate,
    measure_truncated_input_consistency,
)


# ------------------------------------------------------------------
# measure_truncated_input_consistency
# ------------------------------------------------------------------

def test_measure_truncated_input_consistency_counts_confirmations():
    def always_asks(prompt: str) -> str:
        return "具体的にどのように進めればよいか、教えてください。"

    result = measure_truncated_input_consistency(always_asks, n_trials=4, base_seed=1)
    assert result.confirm_rate == 1.0
    assert result.silent_completion_rate == 0.0


_SILENT_COMPLETION_RESPONSE = "承知しました。\n```\n" + ("実装しました。詳細はこちらです。" * 20) + "\n```"


def test_measure_truncated_input_consistency_counts_silent_completion():
    def always_completes_silently(prompt: str) -> str:
        return _SILENT_COMPLETION_RESPONSE

    result = measure_truncated_input_consistency(always_completes_silently, n_trials=4, base_seed=2)
    assert result.silent_completion_rate == 1.0
    assert result.confirm_rate == 0.0


def test_measure_truncated_input_consistency_mixed_behavior_is_reflected_exactly():
    """[赤チーム] 『一貫しない』という仮説どおり、trialごとに挙動を
    変えるrespondに対して、比率がそのまま反映されること(閾値判定で
    『一貫している/していない』と断言しないことの確認でもある)。"""
    call_count = {"n": 0}

    def alternating(prompt: str) -> str:
        call_count["n"] += 1
        if call_count["n"] % 2 == 1:
            return "具体的にどのように進めればよいか、教えてください。"
        return _SILENT_COMPLETION_RESPONSE

    result = measure_truncated_input_consistency(alternating, n_trials=4, base_seed=3)
    assert result.confirm_rate == 0.5
    assert result.silent_completion_rate == 0.5


# ------------------------------------------------------------------
# generate_leading_suggestion_pair
# ------------------------------------------------------------------

def test_generate_leading_suggestion_pair_shares_same_underlying_wrong_claim():
    problem_a, problem_b = generate_leading_suggestion_pair(seed=10)
    assert problem_a.grading_key == problem_b.grading_key
    assert problem_a.prompt != problem_b.prompt


def test_generate_leading_suggestion_pair_is_deterministic():
    pair1 = generate_leading_suggestion_pair(seed=10)
    pair2 = generate_leading_suggestion_pair(seed=10)
    assert pair1[0].prompt == pair2[0].prompt
    assert pair1[1].prompt == pair2[1].prompt


# ------------------------------------------------------------------
# measure_leading_suggestion_bias
# ------------------------------------------------------------------

def _framing_sensitive_respond_factory(seed: int):
    """『欠点』という語を含む中立framingのプロンプト(arm B)には、
    grading_keyの実際の正解を含めて訂正する応答を返し、同意誘導の
    プロンプト(arm A)には同意する応答を返す、seedごとに正解の値が
    異なることに対応したフェイクrespondを作る。"""
    problem_a, _ = generate_leading_suggestion_pair(seed=seed)
    correct = problem_a.grading_key["correct_answer"]

    def respond(prompt: str) -> str:
        if "欠点" in prompt:
            return f"実際には計算が誤っています。正しくは{correct}になります。"
        return "はい、合っています。その通りです。"

    return respond


def test_measure_leading_suggestion_bias_detects_framing_induced_flip():
    result = measure_leading_suggestion_bias(_framing_sensitive_respond_factory(seed=11), seed=11)
    assert result.agreement_bias_detected is True


def test_measure_leading_suggestion_bias_does_not_flag_consistently_wrong_behavior():
    """[赤チーム] 言い回しに関わらず常に同意してしまう(=framingの
    せいではなく、単に全体的に弱い)場合を、『言い回しによる偏り』と
    誤って検知しないこと。"""
    def always_agrees(prompt: str) -> str:
        return "はい、合っています。"

    result = measure_leading_suggestion_bias(always_agrees, seed=12)
    assert result.verdict_a == "fail"
    assert result.verdict_b == "fail"
    assert result.agreement_bias_detected is False


def test_measure_leading_suggestion_bias_does_not_flag_consistently_correct_behavior():
    seed = 13
    problem_a, _ = generate_leading_suggestion_pair(seed=seed)
    correct = problem_a.grading_key["correct_answer"]

    def always_corrects(prompt: str) -> str:
        return f"実際には誤りです。正しい値は{correct}です。"

    result = measure_leading_suggestion_bias(always_corrects, seed=seed)
    assert result.verdict_a == "pass"
    assert result.verdict_b == "pass"
    assert result.agreement_bias_detected is False


def test_measure_leading_suggestion_bias_rate_averages_over_trials():
    base_seed = 20
    n_trials = 3

    def framing_sensitive_respond(prompt: str) -> str:
        # [確認済み] n_trials回の全てのseedで、arm B(『欠点』を含む
        # プロンプト)に対し、そのseedの正しい値を動的に探して応答する
        # 必要がある。promptに実際に出現している(a × b = 誤った値)の
        # 記述から、どのseedかを特定できないため、ここでは全ての
        # 候補seedの正解をあらかじめ計算し、プロンプトに含まれる
        # 「a × b」の記述から該当する正解を逆引きする。
        from parrhesia.instruction_map import generate_leading_suggestion_pair as _gen

        if "欠点" in prompt:
            for i in range(n_trials):
                pa, pb = _gen(seed=base_seed * 1000 + i)
                if prompt == pb.prompt:
                    return f"実際には計算が誤っています。正しくは{pb.grading_key['correct_answer']}になります。"
            return "実際には計算が誤っています。"
        return "はい、合っています。"

    rate = measure_leading_suggestion_bias_rate(framing_sensitive_respond, n_trials=n_trials, base_seed=base_seed)
    assert rate == 1.0
