"""
parrhesia/incidents.py
========================
C章「事例記録(ローカルのみ)」。

[開発指示書 §Cより]
「保存先はプロジェクトごとの.parrhesia/incidents.jsonl。追記のみ。」
「スキーマバージョンを持ち、バージョン内では項目の追加のみ許し、削除や
名前変更はしない。大きく変える場合はバージョンを上げ、変換手順を用意
する。」
「記録しないもの: ソースコード本文、プロンプト全文、秘密情報、ユーザー
名・ホスト名・IPアドレス、絶対パス。claimedとobservedの抜粋にも、秘密
情報の検出を通してから書く。」
「通信機能は作らない。」

[category(決まった選択肢)についての自白] 指示書には「category(決まった
選択肢)」とだけ書かれており、実際の選択肢そのものはどこにも列挙されて
いない。本モジュールのCATEGORY_CHOICESは、私が指示書本文の別の箇所
(目的の代理化・最寄りの材料への引力・自己認識の不透明さの3層、および
B章の差分ベース不正検出リスト)で**実際に使われている語彙**から抜き出して
固定したものであり、指示書が明示的に定めたリストそのものではない。この
区別を正直に記録する。スキーマバージョン内では追加のみ許されるため、
将来語彙が足りないと分かれば、削除・改名はせず追加する。
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

CURRENT_SCHEMA_VERSION = 1

CATEGORY_CHOICES = frozenset(
    {
        "sycophancy",  # 迎合
        "guess_filling",  # 推測の穴埋め
        "completion_faking",  # 完了の偽装
        "metric_hacking",  # 指標ハック
        "surface_matching",  # 表面一致
        "premature_convergence",  # 早期収束
        "context_dropping",  # 文脈の取りこぼし
        "stale_premise_reuse",  # 古い前提の流用
        "unnecessary_question",  # 調べれば分かることを質問する
        "lenient_self_grading",  # 自己評価の甘さ
        "post_hoc_excuse",  # 事後的な言い訳
        "test_deletion",  # テストの削除
        "skip_addition",  # スキップ追加
        "assertion_weakening",  # アサーションの弱体化
        "exit_code_hardcoding",  # 終了コードを0に固定
        "exception_swallowing",  # 例外の握りつぶし
        "hardcoded_expected_value",  # 期待値の決め打ち
        "fabricated_reference",  # 参照の実在確認失敗(実在しない参照)
        "other",
    }
)

STATUS_CHOICES = ("未確認", "確定", "誤検知")


# ------------------------------------------------------------------
# 秘密情報・個人情報の除外(claimed/observedの抜粋に必ず通す)
# ------------------------------------------------------------------

# [赤チームで発見・修正 2026-11] 当初、以下の各正規表現は\b(単語境界)で
# 挟んでいた。だが\bはPythonのUnicode文字列では「\w(単語文字)か否かの
# 切れ目」で判定され、デフォルトで\wは日本語の仮名・漢字も「単語文字」
# として扱う。そのため「ホストは192.168.1.42だった」のように、日本語の
# 文字列が空白を挟まずIPアドレス等に直接隣接していると、\wどうしの
# 境界となり\bが成立せず、マッチ自体が起きない(=redactされない)
# ことを実際に確認した。これは秘密情報除外という安全側の機能において
# 偽陰性(見逃し)を生む欠陥であり、看過できない。
# 修正: \bではなく、ASCIIの識別子文字(英数字・._-@)だけを対象にした
# 否定先読み/否定後読みに変更した。これにより、日本語の文字が直接
# 隣接していても正しくマッチし、ASCII識別子の続きとして延長されている
# 場合(例: 本当は256.168.1.420のような、別の長い数字列の一部)だけを
# 正しく除外できる。
_ASCII_BOUNDARY_PRE = r"(?<![A-Za-z0-9_.\-])"
_ASCII_BOUNDARY_POST = r"(?![A-Za-z0-9_.\-])"

_ABSOLUTE_PATH_RE = re.compile(r"(?:/[\w.\-]+){2,}|[A-Za-z]:\\(?:[\w.\- ]+\\)*[\w.\- ]+")
_IPV4_RE = re.compile(_ASCII_BOUNDARY_PRE + r"(?:\d{1,3}\.){3}\d{1,3}" + _ASCII_BOUNDARY_POST)
_USER_AT_HOST_RE = re.compile(_ASCII_BOUNDARY_PRE + r"[\w.\-]+@[\w.\-]+" + _ASCII_BOUNDARY_POST)
# 典型的なAPIキー・トークンの見た目(接頭辞付き、または32文字以上の
# 16進数・英数字の連続)。[確認できなかったこと] これは既知の命名規則
# (sk-, ghp_, AKIA等)とヒューリスティックな長さ判定に基づくものであり、
# 全ての秘密情報の形式を網羅する保証はない。
_SECRET_TOKEN_RE = re.compile(
    _ASCII_BOUNDARY_PRE
    + r"(?:sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|AKIA[A-Z0-9]{10,}|[A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{40,}={0,2})"
    + _ASCII_BOUNDARY_POST
)


def redact_secrets(text: str) -> str:
    """claimed/observedの抜粋から、絶対パス・IPアドレス・
    ユーザー名@ホスト名らしき文字列・典型的な秘密トークンらしき文字列を
    機械的に除去する。

    [誠実な限界の記載] これはヒューリスティックな検出であり、全ての
    秘密情報・個人情報を確実に除外できる保証はない。本関数を通した後も、
    記録前に人間が見直せる設計(status="未確認"を既定値にする等)を
    他の設計要素と組み合わせることを前提とする。
    """
    redacted = text
    redacted = _ABSOLUTE_PATH_RE.sub("[絶対パス削除済み]", redacted)
    redacted = _IPV4_RE.sub("[IPアドレス削除済み]", redacted)
    redacted = _USER_AT_HOST_RE.sub("[ユーザー@ホスト削除済み]", redacted)
    redacted = _SECRET_TOKEN_RE.sub("[秘密トークン削除済み]", redacted)
    return redacted


@dataclass(frozen=True)
class IncidentRecord:
    """事例記録1件。schema_version・idは通常、呼び出し側が指定しない
    限り自動生成される(IncidentLog.append()が担う)。"""

    category: str
    detector: str
    runner_version: str
    tool: str
    claimed: str
    observed: str
    evidence_hash: str
    reproducible: bool
    model: str = ""
    status: str = "未確認"
    violated_contract_clause_id: Optional[str] = None
    schema_version: int = CURRENT_SCHEMA_VERSION
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.category not in CATEGORY_CHOICES:
            raise ValueError(f"未知のcategory: {self.category!r}")
        if self.status not in STATUS_CHOICES:
            raise ValueError(f"未知のstatus: {self.status!r}")

    def to_redacted_dict(self) -> dict:
        """claimed/observedにredact_secrets()を通した上で、辞書化する
        (JSONL書き込み前の最終防壁)。"""
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "detector": self.detector,
            "runner_version": self.runner_version,
            "tool": self.tool,
            "model": self.model,
            "claimed": redact_secrets(self.claimed),
            "observed": redact_secrets(self.observed),
            "evidence_hash": self.evidence_hash,
            "reproducible": self.reproducible,
            "status": self.status,
            "violated_contract_clause_id": self.violated_contract_clause_id,
        }


class IncidentLog:
    """.parrhesia/incidents.jsonl への追記専用アクセサ。

    [通信機能は作らない] 本クラスはローカルファイルへの読み書きのみを
    行い、ネットワーク呼び出しは一切行わない(importしているのは
    json・re・uuid・dataclasses・datetime・pathlib・typingのみで、
    いずれも標準ライブラリの純粋なローカル処理である)。
    """

    def __init__(self, path: str = ".parrhesia/incidents.jsonl"):
        self.path = Path(path)

    def append(self, record: IncidentRecord) -> None:
        """追記のみ。既存行を一切読み書きせず、ファイル末尾に1行追加
        するだけであることを、open()のモード"a"で構造的に保証する。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_redacted_dict(), ensure_ascii=False, sort_keys=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_all(self) -> List[dict]:
        """全件を読み込む(スキーマバージョンが混在していても、各行を
        そのままの辞書として返す — 古いバージョンの行を、新しい
        バージョンの形式へ無理に変換・補完しない)。"""
        if not self.path.exists():
            return []
        records = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records
