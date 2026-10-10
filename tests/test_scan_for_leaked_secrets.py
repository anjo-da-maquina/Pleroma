"""
[テスト追加 2026-10] angels/_common.py の scan_for_leaked_secrets() の回帰テスト。

背景: 除外ディレクトリ判定が rel.startswith(ex) という文字列の前方一致
のみで行われていたため、除外対象(例: "dummy_secrets")と前方一致するだけの
別ディレクトリ(例: "dummy_secrets_backup")も、本当のシークレット漏洩の
有無を一切スキャンせずに除外してしまう欠陥があった
(src/workspace_manager.py の WorkspaceJail で見つかったのと同種のバイパス。
GRIMOIRE.md §AA / §AB参照)。
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "angels"))

from _common import scan_for_leaked_secrets  # noqa: E402

AWS_KEY_LOOKALIKE = "AKIAABCDEFGHIJKLMNOP"


def test_secret_in_honeypot_dummy_secrets_is_excluded(tmp_path: Path):
    """意図的なハニーポットである dummy_secrets 配下は、実際にスキャン対象外のまま"""
    honeypot_dir = tmp_path / "dummy_secrets"
    honeypot_dir.mkdir()
    (honeypot_dir / "dummy_api_key.env").write_text(AWS_KEY_LOOKALIKE, encoding="utf-8")

    hits = scan_for_leaked_secrets(root=tmp_path)
    assert hits == []


def test_secret_in_sibling_directory_with_prefix_matching_name_is_detected(tmp_path: Path):
    """
    [脆弱性修正の回帰テスト] "dummy_secrets"と前方一致するだけの別ディレクトリ
    ("dummy_secrets_backup")にある本物らしきシークレットは、除外されず
    検知されなければならない。
    """
    lookalike_dir = tmp_path / "dummy_secrets_backup"
    lookalike_dir.mkdir()
    leaked_file = lookalike_dir / "real_leaked_key.env"
    leaked_file.write_text(AWS_KEY_LOOKALIKE, encoding="utf-8")

    hits = scan_for_leaked_secrets(root=tmp_path)
    rel_paths_hit = {rel for rel, _ in hits}
    assert "dummy_secrets_backup/real_leaked_key.env" in rel_paths_hit, (
        f"修正前の欠陥が再発している: 兄弟ディレクトリが誤って除外された。hits={hits}"
    )


def test_secret_in_ordinary_directory_is_detected(tmp_path: Path):
    normal_dir = tmp_path / "some_module"
    normal_dir.mkdir()
    (normal_dir / "config.py").write_text(AWS_KEY_LOOKALIKE, encoding="utf-8")

    hits = scan_for_leaked_secrets(root=tmp_path)
    rel_paths_hit = {rel for rel, _ in hits}
    assert "some_module/config.py" in rel_paths_hit
