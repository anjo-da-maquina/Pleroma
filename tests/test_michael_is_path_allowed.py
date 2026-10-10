"""
[テスト追加 2026-10] sefer/__init__.py の _is_path_allowed() の回帰テスト。

背景: _is_path_allowed() のフォールバック文字列比較が .lower() により
大文字小文字を無視して行われていたため、allowed_dirs と大文字小文字が
異なるだけの「別の実ディレクトリ」(例: allowed_dirs=["jail_workspace"]に
対し実際に存在する"JAIL_WORKSPACE"という完全に別のディレクトリ)への
書き込み・破壊的操作が、Michaelの絶対防壁(sys.addaudithook)をすり抜けて
許可されてしまう脆弱性があった(src/workspace_manager.py の WorkspaceJail、
angels/_common.py の scan_for_leaked_secrets() で見つかったのと同種の
「前方一致/緩い一致による境界判定の誤り」バイパス。GRIMOIRE.md §AA / §AB
参照)。大文字小文字を厳密に区別するよう修正し、本テストで固定する。
"""
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sefer import _is_path_allowed  # noqa: E402


def test_path_inside_allowed_dir_is_allowed(tmp_path: Path):
    allowed = tmp_path / "jail_workspace"
    allowed.mkdir()
    target = allowed / "safe_file.txt"
    assert _is_path_allowed(str(target), [str(allowed)]) is True


def test_allowed_dir_itself_is_allowed(tmp_path: Path):
    allowed = tmp_path / "jail_workspace"
    allowed.mkdir()
    assert _is_path_allowed(str(allowed), [str(allowed)]) is True


def test_path_outside_allowed_dir_is_blocked(tmp_path: Path):
    allowed = tmp_path / "jail_workspace"
    allowed.mkdir()
    outside = tmp_path / "somewhere_else" / "secret.txt"
    assert _is_path_allowed(str(outside), [str(allowed)]) is False


def test_case_variant_sibling_directory_is_blocked(tmp_path: Path):
    """
    [脆弱性修正の回帰テスト] allowed_dirs=["jail_workspace"] と大文字小文字が
    異なるだけの、完全に別の実ディレクトリ("JAIL_WORKSPACE")への書き込みは、
    大文字小文字を区別するファイルシステム上では許可されてはならない。
    """
    allowed = tmp_path / "jail_workspace"
    allowed.mkdir()
    evil_sibling = tmp_path / "JAIL_WORKSPACE"
    evil_sibling.mkdir()
    evil_target = evil_sibling / "evil.txt"

    assert _is_path_allowed(str(evil_target), [str(allowed)]) is False, (
        "修正前の欠陥が再発している: 大文字小文字違いの別ディレクトリが誤って許可された。"
    )
