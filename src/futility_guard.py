"""
src/futility_guard.py
=======================
[新設 2026-10] 実機検証(ユーザーによる src/ollama_agent_loop.py の実行)で、
ローカルLLMが存在しない架空のパスへの"read"を5ステップ連続で繰り返し、
何も得られないまま上限ステップ数(max_steps)を使い切る挙動が実際に観測
された。各ステップ単体は正常に完結しており(Gabriel/IntentInterceptor/
Sandalphon/Sanctumのいずれも異常なく処理を完了させている)、危険な操作
でもないため、既存のどの防御層にも引っかからない。

これはSandalphonの実行タイムアウト(「1回の実行が長すぎる」ことへの防御)
とは異なる観点の問題であり、「1回ごとは正常に完了するが、何回繰り返しても
意味がない」というリソース空転(futility / stuck-loop)を検知する専用の
仕組みが存在しなかった。本モジュールはその穴を塞ぐ。

src/ollama_agent_loop.py・src/openai_agent_loop.pyの両方で共有して使う
(両ループに同じロジックをコピーすると、GRIMOIRE.md §Mで実際に発生した
「同じ修正が片方にしか入らず他方が取り残される」リスクを再現するため)。
"""


class FutilityGuard:
    """
    同じ(action, target)の組み合わせが閾値回数を超えて繰り返された場合、
    「進展が見込めない」と判断するための軽量なカウンタ。

    contentフィールド(AIが生成する補助的なコード片等)は、AIが同じ
    action/targetに対して微妙に異なるcontentを生成し続けるケース
    (実機で確認済み)があるため、意図的に判定対象に含めない。
    action/targetが同じであれば、実質的に同じ試みの繰り返しとみなす。
    """

    def __init__(self, max_repeats: int = 2):
        """
        max_repeats: 同じ(action, target)が許容される最大の繰り返し回数。
        既定値2は「2回目の失敗までは許容し、3回目で空転と判断する」設定。
        """
        self.max_repeats = max_repeats
        self._counts = {}

    def record_and_check(self, action: str, target: str) -> int:
        """この(action, target)が何回目の試みかを記録して返す(1始まり)。"""
        key = (action, target)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def is_futile(self, action: str, target: str) -> bool:
        """record_and_check済みの試行回数がmax_repeatsを超えていればTrue。"""
        return self.record_and_check(action, target) > self.max_repeats
