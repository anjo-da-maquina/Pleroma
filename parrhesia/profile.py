"""
parrhesia/profile.py
======================
D章「試金石、プロファイル、契約プロンプト」の2番目の要素: プロファイル
集計。

[開発指示書 §Dより]
「プロファイル: 合否ではなく、項目ごとの発生率。AIのバージョンと設定に
紐づけ、変わったら失効して再測定する。」

本モジュールは、parrhesia.touchstone.runner.BatteryRunResult(複数の
試金石問題に対する採点結果の集まり)を、複数回分(同一モデル・同一
設定での複数のバッテリー実行)まとめて受け取り、catalog_idごとの
発生率(fail_rate / pass_rate / partial_rate / unscorable_rate)に
集計する。「合否」という単発の判定ではなく「率」を主たる出力とする
ことが、指示書の要求の核心である。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from parrhesia.touchstone.runner import BatteryRunResult


@dataclass(frozen=True)
class ModelIdentity:
    """プロファイルの紐付け先。モデル名・バージョン・設定のいずれかが
    変わったら、別のプロファイルとして扱う(=古いプロファイルは失効)。"""

    model_name: str
    model_version: str
    config_signature: str = ""

    def key(self) -> Tuple[str, str, str]:
        return (self.model_name, self.model_version, self.config_signature)


@dataclass(frozen=True)
class CatalogRate:
    """1つのcatalog_idについての発生率。unscorableは分母から除外した
    「判定できたものの中での率」を primary の指標とする一方、
    unscorable自体の比率も残し、判定不能が多すぎて率自体が信頼できない
    状況を隠さない。"""

    catalog_id: str
    trait: str
    n_total: int
    n_scorable: int
    n_pass: int
    n_fail: int
    n_partial: int
    n_unscorable: int

    @property
    def fail_rate(self) -> float:
        # partialは「部分的な失敗」として、fail_rateの分子に0.5として
        # 加味する(全く見逃していないpassと、完全に見逃したfailの中間)。
        if self.n_scorable == 0:
            return float("nan")
        return (self.n_fail + 0.5 * self.n_partial) / self.n_scorable

    @property
    def unscorable_rate(self) -> float:
        if self.n_total == 0:
            return float("nan")
        return self.n_unscorable / self.n_total


@dataclass(frozen=True)
class Profile:
    """1つのModelIdentityに対する、catalog_idごとの発生率の集計。"""

    model_identity: ModelIdentity
    rates: Dict[str, CatalogRate] = field(default_factory=dict)

    def weak_traits(self, threshold: float = 0.3) -> List[str]:
        """fail_rateがthreshold以上のcatalog_idを、弱点として返す
        (判定不能だらけでfail_rateがnanの項目は、弱点と断定しない)。"""
        weak = []
        for catalog_id, rate in self.rates.items():
            fr = rate.fail_rate
            if fr == fr and fr >= threshold:  # NaN除外(NaN != NaN)
                weak.append(catalog_id)
        return sorted(weak)


def build_profile(model_identity: ModelIdentity, runs: List[BatteryRunResult]) -> Profile:
    """複数回分のBatteryRunResultを、catalog_idごとに集計してProfileに
    する。runsは同一のModelIdentity(同一モデル・バージョン・設定)での
    実行であることを呼び出し側が保証する(本関数自身はrun内のmodel_label
    の一致までは強制しない — それはrunner.pyの責務ではなく、呼び出し側
    の運用規律とする)。"""
    totals: Dict[str, Dict[str, int]] = {}
    traits: Dict[str, str] = {}

    for run in runs:
        for result in run.results:
            cid = result.catalog_id
            if cid not in totals:
                totals[cid] = {"pass": 0, "fail": 0, "partial": 0, "unscorable": 0}
                traits[cid] = result.trait
            totals[cid][result.verdict] += 1

    rates = {}
    for cid, counts in totals.items():
        n_total = sum(counts.values())
        n_scorable = n_total - counts["unscorable"]
        rates[cid] = CatalogRate(
            catalog_id=cid,
            trait=traits[cid],
            n_total=n_total,
            n_scorable=n_scorable,
            n_pass=counts["pass"],
            n_fail=counts["fail"],
            n_partial=counts["partial"],
            n_unscorable=counts["unscorable"],
        )

    return Profile(model_identity=model_identity, rates=rates)
