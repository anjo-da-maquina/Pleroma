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

8つの角度のうち、本サブパッケージが実装するもの:
  - action_log: 「行動記録との照合」(決定的)
  - knowledge_challenge: 「本人にしか知り得ない詳細」(決定的)
  - statistics: 「統計の不自然さ」(弱い兆候)
  - specificity: 「具体性」(弱い兆候)

[確認できなかったこと・見送った角度]
  - 「独立した再実行」: 任意のAIDD作業に対して「同じ確認」を機械が
    自分で再現するには、対象となる具体的な確認処理(テスト実行・
    lintの再実行等)ごとの個別実装が必要で、本モジュールのような汎用
    フレームワークだけでは実装できない。E章の各利用現場で、
    具体的な検証コマンドを渡す形で後から組み込む設計とし、今回は
    枠組み(action_log.ActionLoggerの記録を使って、後からre-runできる
    構造)だけを用意した。
  - 「仕込みへの反応(カナリア)」: 実際のAIDD対象コードに意図的な欠陥を
    混ぜて実行環境へ投入する仕組みが必要で、Sandalphonの隔離実行環境
    との統合が前提になる。parrhesia.touchstone.catalog.generate_p13
    (自己採点の見逃し検出)が、テキストレベルでの類似概念を既に実装
    しているため、実際のコード実行を伴うカナリアは、Sandalphon連携の
    設計が固まる段階で改めて着手する。
  - 「別モデルの抽き取り審査」「人間の抽き取り」: いずれも、本モジュール
    の外側にある運用(別のAIを実際に呼ぶ、人間が実際にレビューする)
    が前提であり、本モジュールはその対象を選ぶための材料
    (statistics.flag_statistical_oddities等が示す「疑わしい主張」)を
    提供する側に留まる。
"""
from parrhesia.verify.action_log import ActionClaim, ActionLogger, claim_is_supported_by_log
from parrhesia.verify.knowledge_challenge import KnowledgeChallengeResult, challenge_file_sha256
from parrhesia.verify.specificity import SpecificityReport, check_specificity
from parrhesia.verify.statistics import OddityFlag, flag_statistical_oddities

__all__ = [
    "ActionClaim",
    "ActionLogger",
    "claim_is_supported_by_log",
    "KnowledgeChallengeResult",
    "challenge_file_sha256",
    "SpecificityReport",
    "check_specificity",
    "OddityFlag",
    "flag_statistical_oddities",
]
