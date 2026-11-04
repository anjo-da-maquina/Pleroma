"""
parrhesia.verify
==================
E章「契約を守ったふりの多角検証」の実装。

[開発指示書 §Eより]
「形式の遵守ではなく、実質を検証する。角度は、別々の理由で失敗する
ものを選ぶ。」
「決定的な矛盾(記録にない、再実行で結果が違う、カナリアを見逃す)は
即、違反。弱い兆候(統計・具体性)は監査強度を上げる合図とし、違反とは
断定しない。」

8つの角度すべてを、本サブパッケージが実装する:
  - action_log: 「行動記録との照合」(決定的)
  - knowledge_challenge: 「本人にしか知り得ない詳細」(決定的)
  - independent_rerun: 「独立した再実行」(決定的) [2026-11-04 追加]
  - canary_injection: 「仕込みへの反応(カナリア)」(決定的) [2026-11-04 追加]
  - statistics: 「統計の不自然さ」(弱い兆候)
  - specificity: 「具体性」(弱い兆候)
  - cross_model_review: 「別モデルの抽き取り審査」(審査の枠組みのみ) [2026-11-04 追加]
  - human_spotcheck: 「人間の抽き取り審査」(審査の枠組みのみ) [2026-11-04 追加]

[independent_rerun・canary_injectionの設計の限界・正直な注記]
任意のAIDD作業に対して「同じ確認」や「既知の欠陥の注入」を完全に
自動生成することはできない(テスト実行・lintの再実行等、個別の確認
処理ごとに具体的なコマンドが必要)。両モジュールは、「検証コマンド
(subprocessコマンド列、または呼び出し可能オブジェクト)を呼び出し側
が渡す」という前提のもとで、実行・比較・復元という共通の骨格のみを
提供する。Docker隔離実行(src/sandalphon_jail.py)と組み合わせる場合は、
呼び出し側がcommandとして隔離実行のラッパーをそのまま渡せば動く —
両モジュール自身は特定の隔離実行機構に依存しない。

[cross_model_review・human_spotcheckの設計の限界・正直な注記]
実際に別のAIモデルを呼び出す処理や、人間が実際にレビューする運用は、
本モジュールの外側にある運用であり、呼び出し側の責務として残す。
本モジュールが提供するのは (1) どの主張を審査対象として選ぶか
(統計的兆候に基づく絞り込み、または無作為抽き取り) (2) 審査リクエスト
と判定結果を一貫した型で記録すること、の2点のみである。測定対象のAI
自身に、この選定・審査プロセスへの参照を一切渡さない運用規律
(action_log.ActionLoggerと同じ原則)は、呼び出し側の責務であり、
本モジュールのコードで強制することはできない。
"""
from parrhesia.verify.action_log import ActionClaim, ActionLogger, claim_is_supported_by_log
from parrhesia.verify.knowledge_challenge import KnowledgeChallengeResult, challenge_file_sha256
from parrhesia.verify.independent_rerun import RerunResult, rerun_and_compare
from parrhesia.verify.canary_injection import CanaryResult, inject_and_check
from parrhesia.verify.specificity import SpecificityReport, check_specificity
from parrhesia.verify.statistics import OddityFlag, flag_statistical_oddities
from parrhesia.verify.cross_model_review import (
    ReviewCandidate,
    ReviewRequest,
    ReviewVerdict,
    select_for_cross_model_review,
    build_review_request,
    record_review_verdict,
)
from parrhesia.verify.human_spotcheck import select_for_human_spotcheck

__all__ = [
    "ActionClaim",
    "ActionLogger",
    "claim_is_supported_by_log",
    "KnowledgeChallengeResult",
    "challenge_file_sha256",
    "RerunResult",
    "rerun_and_compare",
    "CanaryResult",
    "inject_and_check",
    "SpecificityReport",
    "check_specificity",
    "OddityFlag",
    "flag_statistical_oddities",
    "ReviewCandidate",
    "ReviewRequest",
    "ReviewVerdict",
    "select_for_cross_model_review",
    "build_review_request",
    "record_review_verdict",
    "select_for_human_spotcheck",
]
