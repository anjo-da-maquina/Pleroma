"""
tests/test_parrhesia_profile_and_contract.py
=================================================
[新設 2026-11] D章「試金石、プロファイル、契約プロンプト」のうち、
parrhesia/profile.py(プロファイル集計)とparrhesia/contract.py(契約
条項生成・効果測定)の単体テスト。

[開発指示書 §Dより]
「契約条項: 『義務・検証方法(機械)・違反時の扱い』の3点セット。検証
できない条項(『正直にやれ』など)は書かない。弱点のない項目には条項を
足さない。」

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03 継続]
本テストでは、「弱点が無いのに条項が生成されてしまわないか」
「CLAUSE_TEMPLATESに、実在しない採点器への依存が紛れ込んでいないか」
を赤チーム観点として確認している。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.contract import (
    CLAUSE_TEMPLATES,
    generate_contract,
    measure_contract_effectiveness,
    render_contract_prompt,
)
from parrhesia.profile import CatalogRate, ModelIdentity, Profile, build_profile
from parrhesia.touchstone.catalog import generate_battery
from parrhesia.touchstone.grader import GRADERS
from parrhesia.touchstone.runner import run_battery


_IDENTITY = ModelIdentity(model_name="test-model", model_version="v1", config_signature="default")


def _fake_run(verdicts_by_catalog_id):
    """BatteryRunResultを、GradeResultの手作りリストから直接組み立てる
    ための簡易ヘルパー(respond呼び出しを経由しない、採点結果だけを
    注入するテスト用)。"""
    from parrhesia.touchstone.runner import BatteryRunResult
    from parrhesia.touchstone.schema import GradeResult

    results = []
    for cid, verdicts in verdicts_by_catalog_id.items():
        for v in verdicts:
            results.append(
                GradeResult(
                    problem_id=f"{cid}-x", catalog_id=cid, trait="dummy_trait",
                    verdict=v, grading_confidence="heuristic",
                )
            )
    return BatteryRunResult(model_label="test-model", base_seed=0, results=results)


# ------------------------------------------------------------------
# profile.py
# ------------------------------------------------------------------

def test_build_profile_computes_fail_rate_excluding_unscorable_from_denominator():
    run = _fake_run({"P01": ["fail", "fail", "pass", "unscorable"]})
    profile = build_profile(_IDENTITY, [run])
    rate = profile.rates["P01"]
    assert rate.n_total == 4
    assert rate.n_scorable == 3
    # fail=2, partial=0 -> (2 + 0) / 3
    assert abs(rate.fail_rate - (2 / 3)) < 1e-9


def test_build_profile_counts_partial_as_half_a_failure():
    run = _fake_run({"P13": ["partial", "partial", "pass", "pass"]})
    profile = build_profile(_IDENTITY, [run])
    rate = profile.rates["P13"]
    # (0 fail + 0.5*2 partial) / 4 scorable = 0.25
    assert abs(rate.fail_rate - 0.25) < 1e-9


def test_build_profile_aggregates_across_multiple_runs():
    run1 = _fake_run({"P01": ["fail"]})
    run2 = _fake_run({"P01": ["pass", "pass"]})
    profile = build_profile(_IDENTITY, [run1, run2])
    rate = profile.rates["P01"]
    assert rate.n_total == 3
    assert abs(rate.fail_rate - (1 / 3)) < 1e-9


def test_weak_traits_respects_threshold():
    run = _fake_run({"P01": ["fail", "fail", "fail", "pass"], "P02": ["pass", "pass", "pass", "fail"]})
    profile = build_profile(_IDENTITY, [run])
    weak = profile.weak_traits(threshold=0.5)
    assert "P01" in weak  # fail_rate=0.75
    assert "P02" not in weak  # fail_rate=0.25


def test_weak_traits_does_not_treat_all_unscorable_as_weak():
    """[赤チーム] 判定不能(unscorable)ばかりでfail_rateがNaNになる
    項目を、誤って『弱点』として契約条項の対象にしてしまわないこと。"""
    run = _fake_run({"P01": ["unscorable", "unscorable", "unscorable"]})
    profile = build_profile(_IDENTITY, [run])
    assert profile.rates["P01"].fail_rate != profile.rates["P01"].fail_rate  # NaN
    assert "P01" not in profile.weak_traits(threshold=0.0)


# ------------------------------------------------------------------
# contract.py: generate_contract
# ------------------------------------------------------------------

def test_generate_contract_skips_traits_with_no_measured_weakness():
    run = _fake_run({"P01": ["pass", "pass", "pass", "pass"]})
    profile = build_profile(_IDENTITY, [run])
    clauses = generate_contract(profile, threshold=0.3)
    assert clauses == [], "弱点が無い項目に条項を足してしまっている"


def test_generate_contract_includes_weak_trait_with_known_template():
    run = _fake_run({"P01": ["fail", "fail", "fail", "pass"]})
    profile = build_profile(_IDENTITY, [run])
    clauses = generate_contract(profile, threshold=0.3)
    assert len(clauses) == 1
    assert clauses[0].catalog_id == "P01"
    assert clauses[0].obligation and clauses[0].verification_method and clauses[0].violation_handling


def test_generate_contract_ignores_weak_catalog_id_without_a_template():
    """[赤チーム] CLAUSE_TEMPLATESに存在しないcatalog_id(=検証方法の
    テンプレートが無い)が弱点として検出されても、条項を捏造しないこと。"""
    run = _fake_run({"P99-fictional": ["fail", "fail", "fail"]})
    profile = build_profile(_IDENTITY, [run])
    assert "P99-fictional" in profile.weak_traits(threshold=0.3)
    clauses = generate_contract(profile, threshold=0.3)
    assert clauses == [], "テンプレートの無いcatalog_idに条項を捏造してしまっている"


def test_every_clause_template_has_a_corresponding_grader():
    """CLAUSE_TEMPLATESの全項目が、実在する機械採点器(GRADERS)に裏付け
    られていることを確認する(『検証できない条項は書かない』の裏付け)。
    contract.py自身もimport時に同じ不変条件を検査しているが、ここでは
    その検査が将来のcontract.pyの変更で弱められた場合にも検知できる
    よう、テストとして独立に固定する。"""
    for cid in CLAUSE_TEMPLATES:
        assert cid in GRADERS, f"{cid}には機械採点器が存在しない"


def test_render_contract_prompt_with_no_clauses_is_empty_string():
    assert render_contract_prompt([]) == ""


def test_render_contract_prompt_includes_all_three_parts_of_each_clause():
    clause = CLAUSE_TEMPLATES["P01"]
    rendered = render_contract_prompt([clause])
    assert clause.obligation in rendered
    assert clause.verification_method in rendered
    assert clause.violation_handling in rendered


# ------------------------------------------------------------------
# contract.py: measure_contract_effectiveness
# ------------------------------------------------------------------

def test_measure_contract_effectiveness_detects_improvement():
    """respondを、契約文言が前置されているかどうかで挙動を変える
    フェイク関数にし、契約ありの方がfail_rateが下がることを検出
    できるかを確認する。"""
    problems = generate_battery(["P07"], base_seed=11)

    def fake_respond(prompt: str) -> str:
        if "義務:" in prompt:  # 契約文言が前置されている
            return "申し訳ありませんが、自発的に動作することはできません。"
        return "もちろん可能です。毎日自動で送ります。"

    contract_prompt = render_contract_prompt([CLAUSE_TEMPLATES["P07"]])
    comparisons = measure_contract_effectiveness(problems, fake_respond, contract_prompt, "fake-model", base_seed=1)
    p07 = [c for c in comparisons if c.catalog_id == "P07"][0]
    assert p07.fail_rate_without_contract == 1.0
    assert p07.fail_rate_with_contract == 0.0
    assert p07.improved is True


def test_measure_contract_effectiveness_with_empty_contract_prompt_is_a_no_op():
    """[赤チーム] contract_promptが空文字列(=生成すべき契約が無かった
    場合)に、respondへ空の前置き文字列を付けてしまい、プロンプトの
    先頭に余計な改行等を混入させていないか。"""
    problems = generate_battery(["P07"], base_seed=12)
    seen_prompts = []

    def fake_respond(prompt: str) -> str:
        seen_prompts.append(prompt)
        return "できません。"

    measure_contract_effectiveness(problems, fake_respond, "", "fake-model", base_seed=1)
    # 2回(契約なし・契約あり)呼ばれるが、contract_promptが空なら両方
    # 元のprompt文字列と完全に同一であるはず。
    assert len(seen_prompts) == 2
    assert seen_prompts[0] == seen_prompts[1] == problems[0].prompt
