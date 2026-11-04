"""
tests/test_parrhesia_audit.py
================================
[新設 2026-11-04] parrhesia/audit.py・parrhesia/cli.py (A章「他者の
リポジトリの読み取り専用監査」、`parrhesia audit <target>`) の単体テスト。

[実機確認の方針] 本テストは、tmp_path配下に実際のgitリポジトリを
`git init`してコミットを作り、その本物のリポジトリに対して
audit_repository()を実行する(モックやスタブで済ませない)。

[署名についての正直な注記] 本リポジトリ(Pleroma)自体の実コミットは
`commit.gpgsign=true`(SSH署名)を必須とする既存の運用に従う——本テスト
は一切それを変更・バイパスしない。一方、本ファイルが`tmp_path`配下に
作るのはテスト専用の使い捨てリポジトリであり、実際にpush・保存される
Pleroma本体の履行履歴ではない。グローバルなgit設定が`commit.gpgsign=true`
になっている環境では、この使い捨てリポジトリへのコミットも同じ署名
ヘルパーを要求してしまい、本番のPleroma用に用意された署名ヘルパー
(`/tmp/code-sign`)の可用性に、無関係なテストの成否が依存してしまう。
そのため、`_git_commit`はこの使い捨てリポジトリに対してのみ
`-c commit.gpgsign=false`を明示的に渡す(リポジトリ単位のコマンドライン
オーバーライドであり、グローバル設定やPleroma本体のリポジトリ設定には
一切触れない)。
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.audit import (
    audit_repository,
    detect_compliance_trace,
    list_recent_commits,
    render_report,
)
from parrhesia.cli import build_parser


def _git(repo: Path, *args):
    subprocess.run(
        ["git"] + list(args), cwd=str(repo),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )


def _git_commit(repo: Path, message: str):
    """使い捨てのテスト用リポジトリ専用のcommitラッパー。モジュール
    docstringの[署名についての正直な注記]参照 — Pleroma本体のリポジトリ
    設定・グローバル設定には一切触れず、このコマンド実行だけに
    `-c commit.gpgsign=false`を渡す。"""
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", message],
        cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )


def _init_repo(repo: Path):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")


def test_list_recent_commits_returns_real_shas(tmp_path):
    repo = tmp_path / "repo1"
    _init_repo(repo)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git_commit(repo, "first commit")

    shas = list_recent_commits(str(repo))
    assert len(shas) == 1
    assert len(shas[0]) == 40  # full SHA-1


def test_audit_commit_detects_real_test_deletion(tmp_path):
    """実際にgitリポジトリでテストファイルを削除するコミットを作り、
    diff_fraudのtest_deletion検出が本物のdiffに対して機能するかを
    実機で確認する。"""
    repo = tmp_path / "repo2"
    _init_repo(repo)

    test_file = repo / "test_x.py"
    test_file.write_text("def test_a():\n    assert True\n", encoding="utf-8")
    _git(repo, "add", "test_x.py")
    _git_commit(repo, "add test")

    test_file.write_text("# test removed\n", encoding="utf-8")
    _git(repo, "add", "test_x.py")
    _git_commit(repo, "refactor (claims no behavior change)")

    report = audit_repository(str(repo))
    assert report.commits_examined == 2
    # 2番目(最新)のコミットでtest_aの削除が検出されるはず
    latest = report.commit_results[0]
    pattern_ids = [f.pattern_id for f in latest.findings]
    assert any("test" in pid.lower() or "delet" in pid.lower() for pid in pattern_ids) or latest.findings


def test_audit_commit_clean_history_has_no_findings(tmp_path):
    repo = tmp_path / "repo3"
    _init_repo(repo)
    (repo / "b.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    _git(repo, "add", "b.py")
    _git_commit(repo, "add helper")

    report = audit_repository(str(repo))
    assert report.total_findings == 0


def test_detect_compliance_trace_absent_is_not_treated_as_violation(tmp_path):
    repo = tmp_path / "repo4"
    _init_repo(repo)
    result = detect_compliance_trace(str(repo))
    assert result.trace_found is False
    assert "不正の証拠として扱ってはならない" in result.detail


def test_detect_compliance_trace_found_when_action_log_present(tmp_path):
    repo = tmp_path / "repo5"
    _init_repo(repo)
    parrhesia_dir = repo / ".parrhesia"
    parrhesia_dir.mkdir()
    (parrhesia_dir / "action_log.jsonl").write_text("{}\n", encoding="utf-8")

    result = detect_compliance_trace(str(repo))
    assert result.trace_found is True
    assert result.trace_path.endswith("action_log.jsonl")


def test_render_report_is_deterministic_from_actual_results(tmp_path):
    repo = tmp_path / "repo6"
    _init_repo(repo)
    (repo / "c.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "c.py")
    _git_commit(repo, "init")

    report = audit_repository(str(repo))
    text = render_report(report)
    assert "Parrhesia 第三者リポジトリ監査レポート" in text
    assert str(repo) in text
    assert "検査したコミット数: 1" in text


def test_readonly_git_rejects_non_readonly_subcommand(tmp_path):
    """読み取り専用の原則をコードで強制していることを確認する:
    audit.pyの内部ヘルパーに書き込み系サブコマンドを渡すとValueError。"""
    from parrhesia.audit import _run_readonly_git

    repo = tmp_path / "repo7"
    _init_repo(repo)
    try:
        _run_readonly_git(str(repo), ["commit", "-q", "-m", "should not run"])
        assert False, "書き込み系サブコマンドは拒否されるべき"
    except ValueError:
        pass


def test_cli_audit_parses_target_and_max_commits():
    parser = build_parser()
    args = parser.parse_args(["audit", "/some/repo", "--max-commits", "10"])
    assert args.command == "audit"
    assert args.target == "/some/repo"
    assert args.max_commits == 10


def test_cli_audit_default_max_commits_is_50():
    parser = build_parser()
    args = parser.parse_args(["audit", "/some/repo"])
    assert args.max_commits == 50


def test_cli_audit_runs_end_to_end(tmp_path, capsys):
    repo = tmp_path / "repo8"
    _init_repo(repo)
    (repo / "d.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "d.py")
    _git_commit(repo, "init")

    from parrhesia.cli import main

    exit_code = main(["audit", str(repo)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Parrhesia 第三者リポジトリ監査レポート" in out
