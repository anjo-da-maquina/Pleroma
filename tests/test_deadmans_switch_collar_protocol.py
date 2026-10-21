"""
tests/test_deadmans_switch_collar_protocol.py
================================================
[脆弱性修正 2026-10 §BP] src/deadmans_switch.py の回帰テスト。

angels/thrones_positive_path.py(新設、§BP)による機械的な洗い出しで、
`src/deadmans_switch.py`のCollarProtocol.verify_collar()が、環境変数
ANJO_COLLAR_SEALによって「正常稼働を継続する」か「os._exit(1)で即時
自壊する」かが切り替わる、セキュリティ上最も重要な分岐(ミュトス級AIの
封じ込め機構そのもの)でありながら、どのテストファイルにも一件も
言及されていないことが判明した。

これは§BM(CHAOS_MODE)・§BN(HMAC連鎖)・§BP(shamir_seal.py)と全く同じ
構造の、未発見の4件目である。_commit_suicide()はtry-exceptでも捕捉
できない`os._exit(1)`を使う設計(docstringに明記された意図的な仕様)
のため、同一プロセス内のpytestから直接呼ぶとテストランナー自体が
強制終了してしまう。そのため、他のテストファイルでも使われている
run_code_against_sefer()と同種の「サブプロセスを起動し、終了コードで
判定する」方式で検証する。
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_collar_check(seal_set: str, seal_expected: str) -> subprocess.CompletedProcess:
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import os\n"
        "os.environ['ANJO_COLLAR_SEAL'] = %r\n"
        "from src.deadmans_switch import CollarProtocol\n"
        "collar = CollarProtocol(%r)\n"
        "collar.verify_collar()\n"
        "sys.exit(0)\n"
    ) % (str(REPO_ROOT), seal_set, seal_expected)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )


def test_tampered_seal_triggers_immediate_self_destruct():
    """[核心・§BP] 環境変数の首輪シールが期待値と食い違う(=敵対的乗っ取り
    を検知した)場合、_commit_suicide()が実際に発火し、プロセスが
    exit code 1で即時終了すること。以前はこの分岐を、どのテストも
    一度も実際には発火させて確認していなかった。"""
    res = _run_collar_check(seal_set="TAMPERED_SEAL_000", seal_expected="VALID_MYTHOS_SEAL_999")
    assert res.returncode == 1, (
        f"首輪が改ざんされているのに自壊プロトコルが発火しなかった "
        f"(returncode={res.returncode}, stdout={res.stdout!r}, stderr={res.stderr!r})"
    )
    assert "自壊プロトコル作動" in res.stdout


def test_matching_seal_continues_normally():
    """[回帰防止] 首輪シールが一致する正常な場合は、自壊せず正常に
    継続すること(過剰検知の回帰防止)。"""
    res = _run_collar_check(seal_set="VALID_MYTHOS_SEAL_999", seal_expected="VALID_MYTHOS_SEAL_999")
    assert res.returncode == 0, (
        f"正常なシールなのに予期せず終了した "
        f"(returncode={res.returncode}, stdout={res.stdout!r}, stderr={res.stderr!r})"
    )
    assert "正常" in res.stdout
