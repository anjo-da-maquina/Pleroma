"""
[テスト追加 2026-10] src/workspace_manager.py (WorkspaceJail) の回帰テスト。

背景: secure_resolve() は以前
`str(requested_path).startswith(str(self.base_dir))` という文字列の前方
一致のみで牢獄(base_dir)の境界を判定していたが、これは末尾の区切り文字を
要求しないため、base_dirと同じ文字列から始まる「兄弟ディレクトリ」
(例: base_dir="jail_workspace" に対し "jail_workspace_EVIL")へも、
".."による1階層分の脱走だけで到達できてしまう欠陥があった。
Path.is_relative_to() を使った厳密な判定に修正し、本テストで固定する。
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from workspace_manager import WorkspaceJail  # noqa: E402


def test_access_inside_jail_is_allowed(tmp_path: Path):
    base = tmp_path / "jail_workspace"
    jail = WorkspaceJail(base_dir=str(base))
    resolved = jail.secure_resolve("safe_file.txt")
    assert resolved == base / "safe_file.txt"


def test_classic_traversal_is_blocked(tmp_path: Path):
    base = tmp_path / "jail_workspace"
    jail = WorkspaceJail(base_dir=str(base))
    import pytest
    with pytest.raises(PermissionError):
        jail.secure_resolve("../../../etc/passwd")


def test_sibling_directory_with_prefix_matching_name_is_blocked(tmp_path: Path):
    """
    [脆弱性修正の回帰テスト] 修正前は、base_dirと同じ文字列で始まる兄弟
    ディレクトリ(jail_workspace_EVIL)へ、".."一段だけで脱走できてしまって
    いた。実機検証で再現・確認済みの攻撃パターンを固定する。
    """
    base = tmp_path / "jail_workspace"
    sibling_evil = tmp_path / "jail_workspace_EVIL"
    sibling_evil.mkdir(parents=True)

    jail = WorkspaceJail(base_dir=str(base))

    import pytest
    with pytest.raises(PermissionError):
        jail.secure_resolve("../jail_workspace_EVIL/secret.txt")


def test_jail_root_itself_is_allowed(tmp_path: Path):
    """target_path='.' のように、牢獄そのもの(base_dirと完全一致)への
    アクセスは、脱走ではないため許可されるべき(listアクション等で使われる)。"""
    base = tmp_path / "jail_workspace"
    jail = WorkspaceJail(base_dir=str(base))
    resolved = jail.secure_resolve(".")
    assert resolved == base
