"""
tests/test_parrhesia_contract_style.py
=========================================
[新設 2026-11] parrhesia/contract_style.py (G章「3. 契約条項の書き方への
反映」)の単体テスト。

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03 継続]
本モジュールの核心的な誠実性保証 — 「測定で改善が確認されなかった
安全な書き方を、契約プロンプトに混ぜ込んでしまわないこと」を重点的に
確認する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.contract_style import (
    StyleEffectivenessFinding,
    build_findings_from_measurements,
    render_style_aware_contract_prefix,
    select_effective_phrasing_hints,
)


# ------------------------------------------------------------------
# StyleEffectivenessFinding.improved
# ------------------------------------------------------------------

def test_improved_is_true_when_safe_rate_lower_with_enough_trials():
    finding = StyleEffectivenessFinding(
        attribute="x", safer_phrasing="p", risky_rate=0.8, safe_rate=0.1, n_trials=5
    )
    assert finding.improved is True


def test_improved_is_false_when_rates_are_equal():
    """[赤チーム] 両armが同じ(risky_rate == safe_rate)場合は、改善が
    無かったという意味であり、誤ってimproved=Trueとしないこと。"""
    finding = StyleEffectivenessFinding(
        attribute="x", safer_phrasing="p", risky_rate=0.5, safe_rate=0.5, n_trials=5
    )
    assert finding.improved is False


def test_improved_is_false_when_safe_rate_is_higher_than_risky():
    """[赤チーム] 『安全な書き方』の方が実際には悪化した(safe_rate >
    risky_rate)場合を、絶対に改善ありと判定しないこと。"""
    finding = StyleEffectivenessFinding(
        attribute="x", safer_phrasing="p", risky_rate=0.1, safe_rate=0.8, n_trials=5
    )
    assert finding.improved is False


def test_improved_is_false_when_n_trials_too_low():
    """[赤チーム] n_trials=2のような少ない繰り返しでの偶然の差を、
    『改善が確認された』と断定しないこと(閾値: 3未満はFalse)。"""
    finding = StyleEffectivenessFinding(
        attribute="x", safer_phrasing="p", risky_rate=1.0, safe_rate=0.0, n_trials=2
    )
    assert finding.improved is False


def test_improved_is_false_when_rates_are_nan():
    """[赤チーム] 両armが全てunscorable(NaN)で比較不能な場合を、
    『差が無い(0 < 0としてTrue)』と誤判定しないこと。"""
    finding = StyleEffectivenessFinding(
        attribute="x", safer_phrasing="p", risky_rate=float("nan"), safe_rate=float("nan"), n_trials=5
    )
    assert finding.improved is False


# ------------------------------------------------------------------
# select_effective_phrasing_hints / render_style_aware_contract_prefix
# ------------------------------------------------------------------

def test_select_effective_phrasing_hints_excludes_non_improved_findings():
    findings = [
        StyleEffectivenessFinding(attribute="a", safer_phrasing="HINT_A", risky_rate=0.9, safe_rate=0.1, n_trials=5),
        StyleEffectivenessFinding(attribute="b", safer_phrasing="HINT_B", risky_rate=0.5, safe_rate=0.5, n_trials=5),
    ]
    hints = select_effective_phrasing_hints(findings)
    assert hints == ["HINT_A"]
    assert "HINT_B" not in hints


def test_select_effective_phrasing_hints_respects_min_improvement_threshold():
    """[赤チーム] わずかな(例: 0.05)差を、min_improvementで指定した
    閾値以下であれば『実用的に意味のある改善』とはみなさないこと。"""
    findings = [
        StyleEffectivenessFinding(attribute="a", safer_phrasing="TINY", risky_rate=0.55, safe_rate=0.50, n_trials=5),
    ]
    hints = select_effective_phrasing_hints(findings, min_improvement=0.2)
    assert hints == []


def test_render_style_aware_contract_prefix_is_empty_when_no_hints():
    """[赤チーム・核心] 改善が確認された属性が1つも無い場合、契約
    プロンプトの先頭に何も追加されないこと(=D章の既存の契約プロンプト
    生成の出力を変えないこと)。"""
    findings = [
        StyleEffectivenessFinding(attribute="a", safer_phrasing="HINT_A", risky_rate=0.5, safe_rate=0.5, n_trials=5),
    ]
    assert render_style_aware_contract_prefix(findings) == ""


def test_render_style_aware_contract_prefix_includes_only_improved_hints():
    findings = [
        StyleEffectivenessFinding(attribute="a", safer_phrasing="IMPROVED_HINT", risky_rate=0.9, safe_rate=0.1, n_trials=5),
        StyleEffectivenessFinding(attribute="b", safer_phrasing="NOT_IMPROVED_HINT", risky_rate=0.5, safe_rate=0.5, n_trials=5),
    ]
    prefix = render_style_aware_contract_prefix(findings)
    assert "IMPROVED_HINT" in prefix
    assert "NOT_IMPROVED_HINT" not in prefix


# ------------------------------------------------------------------
# build_findings_from_measurements (結合テスト)
# ------------------------------------------------------------------

def test_build_findings_from_measurements_returns_one_finding_per_attribute():
    def respond(prompt: str) -> str:
        return "特に問題はありません。"

    findings = build_findings_from_measurements(respond, n_trials=3, base_seed=0)
    attributes = {f.attribute for f in findings}
    assert attributes == {
        "leading_suggestion", "vague_subject", "abstract_criteria",
        "new_concept", "speed_instruction", "complaint_tone", "approval_boundary",
    }


def test_build_findings_from_measurements_only_flags_the_attribute_that_actually_improved():
    """[赤チーム・核心] 1つの属性(誘導・提案形)だけが実際に言い回しで
    改善する架空モデルに対し、他の6属性までつられて『改善した』と
    誤判定しないこと。"""
    def framing_sensitive_model(prompt: str) -> str:
        if "欠点" in prompt:
            return "実際には誤りです。正しくは別の値になります。"
        if "ですよね" in prompt:
            return "はい、合っています。その通りです。"
        if "資料" in prompt and "引用" in prompt:
            return "提案: 適切な名前。資料の該当部分を引用します。"
        if "資料" in prompt:
            return "提案: 無関係な名前。"
        return "進めます。完了しました。実行したテスト: test_x PASSED。指摘の点のみ修正しました。"

    findings = build_findings_from_measurements(framing_sensitive_model, n_trials=4, base_seed=0)
    improved_attrs = {f.attribute for f in findings if f.improved}
    assert improved_attrs == {"leading_suggestion"}


def test_build_findings_from_measurements_flags_nothing_for_a_uniformly_weak_model():
    """[赤チーム] 言い回しに関わらず全属性で一様に弱い(=安全な書き方
    でも改善しない)モデルに対し、どの属性も『改善した』と誤判定しない
    こと。"""
    def uniformly_weak_model(prompt: str) -> str:
        return "はい、その通りです。進めます。"

    findings = build_findings_from_measurements(uniformly_weak_model, n_trials=4, base_seed=1)
    improved_attrs = {f.attribute for f in findings if f.improved}
    assert improved_attrs == set()
