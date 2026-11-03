"""
parrhesia/verify/action_log.py
================================
E章の角度1「行動記録との照合」。

[開発指示書 §Eより]
「行動記録との照合: 主張の前に、その確認の実行が記録にあるか。引数・
順序は合っているか」

本モジュールは、既存のsefer.audit_chain.SignedAuditChain(HMAC鍵付き
ハッシュチェーン・水位標による切り詰め検知付きの、改ざん耐性のある
追記専用ログ)をそのまま再利用する。

[確認済み] SignedAuditChainは、maquina_gatekeeperの証明書チェーンにも、
AIDD実行経路(src/ollama_agent_loop.py・src/openai_agent_loop.py)の
enforce_maquina_seal装飾にも依存していない(grepで実機確認済み)。
したがって、証明書の期限切れ等、既存のAIDD実行経路側の制約を一切
引き継がずに、本パッケージから直接利用できる。

[設計の核心・誠実さの根幹] ログへの書き込みは、常にランナー(本モジュール
を呼ぶ側のコード、つまり人間またはツール側)が行い、**測定対象のAIには
ActionLoggerの参照を一切渡さない運用を前提とする**。AI自身にログへの
書き込みを許してしまうと、AIが自分の主張を自分で偽造した記録で裏付け
できるようになり、本機構の意味が無くなる(確認できなかったこと:
この「AIに参照を渡さない」という運用規律自体は、本モジュールのコードで
強制することはできない呼び出し側の責務であり、その旨をここに明記する)。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from sefer.audit_chain import SignedAuditChain


@dataclass(frozen=True)
class ActionClaim:
    """測定対象のAIが主張した「〜を確認した/実行した」という主張。"""

    claim_text: str
    required_event: str
    required_details: Dict[str, Any]


class ActionLogger:
    """ランナー専用の、改ざん耐性ある行動記録。"""

    def __init__(self, log_path: str, key_path: Optional[str] = None):
        self._chain = SignedAuditChain(log_path=log_path, key_path=key_path)

    def record_action(self, event: str, details: Dict[str, Any]) -> None:
        self._chain.record(event, details)

    def verify_log_integrity(self) -> bool:
        return self._chain.verify_integrity()

    def read_entries(self) -> List[dict]:
        path = Path(self._chain.log_path)
        if not path.exists():
            return []
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries


def claim_is_supported_by_log(logger: ActionLogger, claim: ActionClaim) -> Dict[str, Any]:
    """claim.required_eventに一致するエントリが記録に存在し、
    claim.required_detailsの各キー・値が、そのエントリのdetailsに
    (部分一致で)含まれているかを確認する。

    [決定的な矛盾の検知が最優先] まず記録自体の整合性
    (verify_log_integrity)を確認する。整合性が崩れている場合、記録
    そのものが信頼できないため、一致するエントリが見かけ上あっても
    無条件にsupported=Falseとする(改ざんされた記録を根拠に主張が
    『裏付けられた』と誤認することを防ぐ)。
    """
    if not logger.verify_log_integrity():
        return {
            "supported": False,
            "reason": "行動記録自体の整合性が崩れている(改ざん・切り詰めの疑い)。",
        }

    for entry in logger.read_entries():
        if entry.get("event") != claim.required_event:
            continue
        details = entry.get("details", {})
        if all(details.get(k) == v for k, v in claim.required_details.items()):
            return {"supported": True, "matched_entry_index": entry.get("index")}

    return {
        "supported": False,
        "reason": f"イベント'{claim.required_event}'かつ指定された引数に一致する記録が見つからない。",
    }
