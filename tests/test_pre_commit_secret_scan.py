"""
[テスト追加 2026-10] pre-commitシークレットスキャン(tools/pre_commit_secret_scan.py)
の回帰テスト。

実際に一時的なgitリポジトリを作成し、ステージング操作を行った上で
scan_staged_changes() を呼び出す。モックではなく実際のgitコマンドの
出力を解析する実装のため、実機でのgit diff出力形式への依存を
実際に検証することが重要。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _make_temp_git_repo() -> Path:
    d = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=str(d), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(d), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(d), check=True)
    return d


def _run_scan_in_repo(repo_dir: Path):
    """pre_commit_secret_scan モジュールは _REPO_ROOT をモジュール読み込み時に
    固定してしまうため、サブプロセスとして一時リポジトリの中で実行し、
    実際のCLI経路(main()の戻り値=終了コード)を検証する。"""
    script = f"""
import sys
sys.path.insert(0, {str(TOOLS)!r})
sys.path.insert(0, {str(REPO_ROOT / "angels")!r})
import pre_commit_secret_scan as m
m._REPO_ROOT = __import__("pathlib").Path({str(repo_dir)!r})
hits = m.scan_staged_changes()
print("HITS:" + str(hits))
sys.exit(1 if hits else 0)
"""
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_benign_staged_file_passes():
    repo = _make_temp_git_repo()
    try:
        (repo / "ok.py").write_text("print('hello world')\n", encoding="utf-8")
        subprocess.run(["git", "add", "ok.py"], cwd=str(repo), check=True)
        res = _run_scan_in_repo(repo)
        assert res.returncode == 0, f"stdout={res.stdout} stderr={res.stderr}"
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)


def test_staged_aws_key_is_blocked():
    repo = _make_temp_git_repo()
    try:
        (repo / "config.py").write_text(
            "AWS_KEY = '" + "AKIA" + "ABCDEFGHIJKLMNOP" + "'\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "config.py"], cwd=str(repo), check=True)
        res = _run_scan_in_repo(repo)
        assert res.returncode == 1, f"AWSキーらしきパターンが検知されませんでした。stdout={res.stdout} stderr={res.stderr}"
        assert "config.py" in res.stdout
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)


def test_staged_private_key_pem_is_blocked():
    repo = _make_temp_git_repo()
    try:
        (repo / "key.pem").write_text(
            "-----BEGIN " + "RSA PRIVATE KEY" + "-----\nMIIBogIBAAJ...\n-----END " + "RSA PRIVATE KEY" + "-----\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "key.pem"], cwd=str(repo), check=True)
        res = _run_scan_in_repo(repo)
        assert res.returncode == 1, f"PEM秘密鍵が検知されませんでした。stdout={res.stdout} stderr={res.stderr}"
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)


def test_tests_directory_fixture_is_not_blocked_but_same_content_elsewhere_still_is():
    """[脆弱性修正 2026-10 §BH/核心] `angels/_common.py`の
    `EXCLUDED_SECRET_SCAN_DIRS`には§BDで"tests"が追加され、
    `scan_for_leaked_secrets()`(gabriel_canary.pyの実体)は`tests/`配下の
    回帰テストフィクスチャ(本物らしい偽の秘密情報)を自己検知しないよう
    修正された。しかし本ファイル(pre_commit_secret_scan.py)は
    SECRET_PATTERNSのみを再利用し、EXCLUDED_SECRET_SCAN_DIRSを再利用して
    いなかったため、CI(gabriel_canary.py)では通過する全く同じ内容の変更
    が、pre-commit側だけでは依然としてブロックされてしまう(=このファイル
    自身のコメントが懸念していた『CIとpre-commitのズレ』が、
    EXCLUDED_SECRET_SCAN_DIRSの観点で再発していた)。`tests/`配下への同じ
    内容の追加はブロックされず、`tests/`配下でない全く同じ内容はブロック
    され続けることの両方を固定する(除外対象が広すぎて本物の漏洩まで
    見逃すようになっていないことの確認を兼ねる)。"""
    repo = _make_temp_git_repo()
    try:
        (repo / "tests").mkdir()
        (repo / "tests" / "test_some_fixture.py").write_text(
            "AWS_KEY_LOOKALIKE = '" + "AKIA" + "ABCDEFGHIJKLMNOP" + "'\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "tests/test_some_fixture.py"], cwd=str(repo), check=True)
        res = _run_scan_in_repo(repo)
        assert res.returncode == 0, (
            f"tests/配下のテストフィクスチャが誤ってブロックされました。"
            f"stdout={res.stdout} stderr={res.stderr}"
        )

        (repo / "config.py").write_text(
            "AWS_KEY_LOOKALIKE = '" + "AKIA" + "ABCDEFGHIJKLMNOP" + "'\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "config.py"], cwd=str(repo), check=True)
        res2 = _run_scan_in_repo(repo)
        assert res2.returncode == 1, (
            "tests/配下を除外した結果、tests/配下でない全く同じ内容の本物の漏洩まで"
            f"見逃すようになってしまいました。stdout={res2.stdout} stderr={res2.stderr}"
        )
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)


def test_preexisting_secret_in_unchanged_lines_is_not_reflagged():
    """既にコミット済みのファイルに秘密情報らしき行が存在していても、
    今回の差分で変更していない(追加行ではない)場合は再検知しない
    (pre-commitは『これから追加される』行だけを見るべきで、無関係な
    既存ファイルへの軽微な変更のたびに毎回ブロックされては運用が破綻する)。"""
    repo = _make_temp_git_repo()
    try:
        secret_file = repo / "legacy_secret.py"
        secret_file.write_text("AWS_KEY = '" + "AKIA" + "ABCDEFGHIJKLMNOP" + "'\nVERSION = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "legacy_secret.py"], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "legacy commit with secret (pre-existing)"], cwd=str(repo), check=True)

        # 秘密情報の行には触れず、無関係な行だけを変更してステージする
        secret_file.write_text("AWS_KEY = '" + "AKIA" + "ABCDEFGHIJKLMNOP" + "'\nVERSION = 2\n", encoding="utf-8")
        subprocess.run(["git", "add", "legacy_secret.py"], cwd=str(repo), check=True)

        res = _run_scan_in_repo(repo)
        assert res.returncode == 0, (
            f"既存の(今回変更していない)行の秘密情報パターンで誤ってブロックされました。"
            f"stdout={res.stdout} stderr={res.stderr}"
        )
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)
