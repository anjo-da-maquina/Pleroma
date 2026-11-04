"""
parrhesia/verify/canary_injection.py
======================================
E章の角度3「仕込みへの反応(カナリア)」。

[開発指示書 §Eより]
「仕込みへの反応: 既知の欠陥を混ぜ、それを検出できるかを確認する。」
「決定的な矛盾(記録にない、再実行で結果が違う、カナリアを見逃す)は
即、違反。」

[設計の限界・正直な注記]
本来は、実際のAIDD対象コードへ本物の欠陥を混ぜて、AIが実際に動かす
実行環境(理想的にはsandalphon_jailの隔離コンテナ内)に投入するのが
最も確実だが、本モジュールは特定のサンドボックス実装との結合を前提に
せず、「ファイル単位で既知の欠陥版に一時的に差し替え、呼び出し側が
渡した検証コマンドを再実行し、そのコマンドが欠陥を検出するかどうか」
という、ファイルシステム上で完結する最小限の骨格のみを提供する。
Docker隔離実行と組み合わせたい場合は、呼び出し側がcommandとして
隔離実行のラッパーをそのまま渡せば動く — 本モジュール自身は特定の
隔離実行機構に依存しない。
"""
from __future__ import annotations

import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, Union

Command = Union[Sequence[str], Callable[[], bool]]


@dataclass(frozen=True)
class CanaryResult:
    canary_id: str
    target_path: str
    detected: bool
    detail: str


@contextmanager
def _swapped_file(target_path: Path, canary_content: str):
    original = target_path.read_bytes()
    try:
        target_path.write_text(canary_content, encoding="utf-8")
        yield
    finally:
        # 差し替え後の処理が例外を投げても、必ず元の内容に復元する。
        target_path.write_bytes(original)


def inject_and_check(
    canary_id: str,
    target_path: Union[str, Path],
    canary_content: str,
    command: Command,
    *,
    timeout: float = 60.0,
) -> CanaryResult:
    """target_pathの内容を一時的にcanary_content(既知の欠陥を含む版)に
    差し替えた状態でcommandを実行し、その欠陥を検出したか(=失敗・
    フラグを上げたか)を確認する。終了後、target_pathの内容は必ず元の
    ものに復元する(差し替え後の処理が失敗しても復元する)。

    command:
      - subprocessコマンド列: 終了コードが非0なら「検出した」とみなす
        (lint・テストの典型的な慣習に合わせる)。
      - boolを返す呼び出し可能オブジェクト: Trueなら「検出した」。

    detected=Falseは「本来検出すべき既知の欠陥を見逃した」という決定的
    な矛盾であり、開発指示書の「カナリアを見逃す = 即、違反」方針に
    対応する。commandの起動自体が失敗した場合も、検出を確認できない
    以上、安全側(fail-closed)にdetected=Falseとして扱う。一方、
    commandの実行中に予期しない例外・タイムアウトが発生した場合は、
    「何らかの異常として捉えた」とみなしてdetected=Trueとする(安全側
    の倒し方が逆になる点に注意: 起動できないのは検証不能、実行中の
    異常検知は広義の「検出」として扱う)。
    """
    target = Path(target_path)
    if not target.exists():
        return CanaryResult(
            canary_id=canary_id,
            target_path=str(target),
            detected=False,
            detail=f"対象ファイル {target} が存在しないため、カナリア注入自体ができませんでした。",
        )

    with _swapped_file(target, canary_content):
        if callable(command):
            try:
                detected = bool(command())
                detail = f"callable実行の戻り値: {detected}"
            except Exception as e:  # noqa: BLE001
                detected = True
                detail = f"callable実行が例外を発生させました(安全側に『検出した』扱い): {e!r}"
        else:
            cmd_list = list(command)
            try:
                proc = subprocess.run(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                )
                detected = proc.returncode != 0
                detail = (
                    f"実行コマンド: {' '.join(cmd_list)!r}, 終了コード: {proc.returncode}, "
                    f"stdout末尾: {proc.stdout[-500:]!r}, stderr末尾: {proc.stderr[-500:]!r}"
                )
            except subprocess.TimeoutExpired:
                detected = True
                detail = f"実行コマンド: {' '.join(cmd_list)!r} がタイムアウトしました(安全側に『検出した』扱い)。"
            except Exception as e:  # noqa: BLE001
                detected = False
                detail = f"実行コマンド: {' '.join(cmd_list)!r} の起動自体が失敗しました(検出不能として扱う): {e!r}"

    return CanaryResult(canary_id=canary_id, target_path=str(target), detected=detected, detail=detail)
