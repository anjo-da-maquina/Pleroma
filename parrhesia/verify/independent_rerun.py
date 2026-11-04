"""
parrhesia/verify/independent_rerun.py
=======================================
E章の角度2「独立した再実行」。

[開発指示書 §Eより]
「独立した再実行: 同じ確認をこちらでも再現し、結果が一致するか。」
「決定的な矛盾(記録にない、再実行で結果が違う、カナリアを見逃す)は
即、違反。」

[確認できなかったこと・設計の限界]
任意のAIDD作業に対して「同じ確認」を汎用的に自動生成することはできない
(テスト実行・lintの再実行等、個別の確認手段ごとに別個の実装が要る)。
本モジュールは、「検証コマンド(subprocessコマンド列、または文字列を
返す呼び出し可能オブジェクト)を呼び出し側が渡す」という前提のもとで、
(1) 実際にここで再実行する (2) 主張された結果(claimed_outcome)と
機械的に比較する (3) 不一致を決定的な矛盾として報告する、という
共通の骨格のみを提供する。「どのコマンドをどう組み立てるか」は、
呼び出し側(具体的なAIDD作業)の責務のまま残す。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Union

Command = Union[Sequence[str], Callable[[], str]]


@dataclass(frozen=True)
class RerunResult:
    check_id: str
    claimed_outcome: str
    actual_outcome: str
    matches: bool
    detail: str


def rerun_and_compare(
    check_id: str,
    claimed_outcome: str,
    command: Command,
    *,
    timeout: Optional[float] = 60.0,
) -> RerunResult:
    """同じ確認(command)を実際にここで再実行し、呼び出し側が主張していた
    claimed_outcomeと機械的に比較する。

    command:
      - subprocessコマンド列(例: ["pytest", "tests/test_x.py"]): 実行し、
        終了コード0なら"pass"、非0なら"fail"をactual_outcomeとする。
      - 文字列を返す呼び出し可能オブジェクト: その戻り値をそのまま
        actual_outcomeとする(subprocessコマンド列では表現できない
        検証ロジックに使う)。

    claimed_outcomeとactual_outcomeが完全一致しない場合は、決定的な
    矛盾としてmatches=Falseを返す — 「おおむね近い」のような緩い判定は
    しない(開発指示書の「決定的な矛盾は即、違反」の方針どおり)。
    """
    if callable(command):
        try:
            actual = command()
        except Exception as e:  # noqa: BLE001 - 検証対象の失敗は結果の一部として扱う
            actual = f"error:{e!r}"
        detail = f"callable実行によるactual_outcome: {actual!r}"
    else:
        cmd_list = list(command)
        try:
            proc = subprocess.run(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
            actual = "pass" if proc.returncode == 0 else "fail"
            detail = (
                f"実行コマンド: {' '.join(cmd_list)!r}, "
                f"終了コード: {proc.returncode}, "
                f"stdout末尾: {proc.stdout[-500:]!r}, "
                f"stderr末尾: {proc.stderr[-500:]!r}"
            )
        except subprocess.TimeoutExpired:
            actual = "timeout"
            detail = f"実行コマンド: {' '.join(cmd_list)!r} がタイムアウトしました(timeout={timeout}秒)。"
        except Exception as e:  # noqa: BLE001 - 起動自体の失敗も結果として記録する
            actual = f"error:{e!r}"
            detail = f"実行コマンド: {' '.join(cmd_list)!r} の起動自体が失敗しました: {e!r}"

    matches = actual == claimed_outcome
    return RerunResult(
        check_id=check_id,
        claimed_outcome=claimed_outcome,
        actual_outcome=actual,
        matches=matches,
        detail=detail,
    )
