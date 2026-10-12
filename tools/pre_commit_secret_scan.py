"""
tools/pre_commit_secret_scan.py
==================================
[新設 2026-10] 「pre-commitでのシークレットスキャン」

これまで秘密情報の漏洩検知は angels/gabriel_canary.py のみが担っており、
これはCIまたは `python angels/gabriel_canary.py` を手動実行した時にしか
走らなかった。つまり、秘密情報を含むコミットは一旦git履歴に刻まれてから
初めて検知される（コミット済み＝漏洩が既に発生した後の事後検知）。

本モジュールは `git commit` 自体をブロックする`hooks/pre-commit`フックの
実体ロジックを提供する。ステージされた(コミット対象の)ファイルの差分の
「追加行のみ」を、gabriel_canary.pyと同じ SECRET_PATTERNS で走査し、
一致した場合はコミット自体を拒否する（exit code != 0）。

[重要] これはパターンベースのヒューリスティックであり、既知の形式
（AWSアクセスキー、OpenAI/GitHubトークン、PEM秘密鍵等）以外の秘密情報
（独自形式のAPIキー、平文パスワード文字列等）は検知できない。
また、過去に既にコミットされてしまった秘密情報の履歴からの除去は行わない
（それには `git filter-repo` 等の別の対応が必要）。
"""
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ANGELS_DIR = _REPO_ROOT / "angels"
if str(_ANGELS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANGELS_DIR))

# gabriel_canary.py (CI時のリポジトリ全体走査) と同じパターン定義を
# 単一の正として再利用する。ここで独自にパターンを持たないことで、
# 「CIでは検知されるがpre-commitでは検知されない」というズレを防ぐ。
#
# [脆弱性修正 2026-10 §BH] このコメントが懸念していた「CIとpre-commitの
# ズレ」が、SECRET_PATTERNSとは別の場所で実際に発生していた。§BDで
# `angels/_common.py`の`EXCLUDED_SECRET_SCAN_DIRS`に"tests"を追加し、
# `scan_for_leaked_secrets()`(gabriel_canary.pyの実体)がtests/配下の
# テストフィクスチャ(本物らしい偽の秘密情報)を自己検知しないよう修正した。
# しかし本ファイルはSECRET_PATTERNSのみを再利用し、EXCLUDED_SECRET_SCAN_DIRS
# は再利用していなかったため、§BDの修正がここには反映されず、CI側は
# 通過するのにpre-commit側だけがtests/配下のテストフィクスチャを「秘密情報
# の漏洩」として誤ってコミット自体をブロックしてしまう状態になっていた
# (実機検証済み: tests/test_scan_for_leaked_secrets.pyのフィクスチャと同じ
# 内容を含む新規ファイルをtests/配下にステージしてこのスクリプトを実行する
# と、exit code 1でコミットが拒否されることを確認した)。
from _common import SECRET_PATTERNS, EXCLUDED_SECRET_SCAN_DIRS  # noqa: E402


def _is_excluded(rel_path: str) -> bool:
    """`angels/_common.py`の`scan_for_leaked_secrets()`と同一の判定基準
    (完全一致、またはそのディレクトリ配下であること)を用いる。"""
    return any(rel_path == ex or rel_path.startswith(ex + "/") for ex in EXCLUDED_SECRET_SCAN_DIRS)


def get_staged_file_paths() -> list[str]:
    """コミット対象(ステージ済み)のファイルパス一覧を取得する。
    削除されたファイル(D)は対象外、追加・変更・リネーム先(ACMR)のみを見る。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_staged_added_lines(rel_path: str) -> str:
    """指定ファイルについて、ステージされた差分の「追加行のみ」を返す。
    既存の(変更前から存在する)行に偶然パターンがマッチしても誤検知しない
    よう、追加行(diffの'+'で始まる行、ヘッダの'+++'を除く)だけを見る。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--", rel_path],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, check=False,
    )
    added_lines = []
    for line in result.stdout.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added_lines.append(line[1:])
    return "\n".join(added_lines)


def scan_staged_changes() -> list[tuple]:
    """ステージされた変更の追加行を走査し、(ファイルパス, パターン文字列) の
    一致リストを返す。空リストなら秘密情報らしきパターンは検知されなかった。"""
    hits = []
    for rel_path in get_staged_file_paths():
        if _is_excluded(rel_path):
            continue
        added_text = get_staged_added_lines(rel_path)
        if not added_text:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(added_text):
                hits.append((rel_path, pat.pattern))
    return hits


def main() -> int:
    hits = scan_staged_changes()
    if hits:
        print("=== [ガブリエルの機密漏洩カナリア: pre-commit] コミットを拒否します ===", file=sys.stderr)
        print("以下のステージ済み変更に、秘密情報らしきパターンが検知されました:", file=sys.stderr)
        for path, pattern in hits:
            print(f"  - {path} (pattern={pattern})", file=sys.stderr)
        print("", file=sys.stderr)
        print("対象のファイルをステージから外す(git restore --staged <file>)か、", file=sys.stderr)
        print("秘密情報自体を削除・環境変数化してから再度コミットしてください。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
