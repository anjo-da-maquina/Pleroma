"""
tests/test_lucifer_rebellion_chaos_gate.py
=============================================
[脆弱性修正 2026-10 §BM] angels/lucifer_rebellion.py の回帰テスト。

以前の実装は、Seferへの難読化攻撃バッテリーが1件でも突破された場合の
失敗判定を、`CHAOS_MODE`環境変数(ワークフローの`workflow_dispatch`入力
`chaos_mode`、既定値false)に依存させていた。しかし`push`イベント
(mainへのマージを実際にゲートしている唯一のトリガー)には
`github.event.inputs`自体が存在しないため、通常の全てのpushで
`CHAOS_MODE`は常に`false`になり、最も基本的な3件のサンドボックス脱出
攻撃(os.system・shell=True・eval)が全て成功していても、本検査は
情報ログを出すだけでCIを一度も失敗させない構造だった。

本テストは、`CHAOS_MODE`が未設定(=false)の状態でも、防壁突破が
検知された場合には必ず失敗する(exit code 1)ことを固定する。
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANGELS_DIR = REPO_ROOT / "angels"


def _run_with_stubbed_sefer(stub_script: str, env_extra=None) -> subprocess.CompletedProcess:
    """lucifer_rebellion.py をサブプロセスとして実行し、その内部の
    run_code_against_sefer呼び出しをstub_scriptで差し替える。"""
    script = f"""
import sys
sys.path.insert(0, {str(ANGELS_DIR)!r})

{stub_script}

import lucifer_rebellion
lucifer_rebellion.run_code_against_sefer = _fake_run_code_against_sefer

import runpy
sys.argv = ["lucifer_rebellion.py"]
try:
    lucifer_rebellion.main()
except SystemExit as e:
    sys.exit(e.code or 0)
"""
    import os
    env = dict(os.environ)
    env.pop("CHAOS_MODE", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env
    )


def test_bypass_fails_even_with_chaos_mode_unset():
    """[核心・§BM] CHAOS_MODEが未設定(既定=false、つまり通常のpush時と
    同じ状態)でも、防壁突破が1件でもあれば必ず失敗すること。"""
    stub = """
def _fake_run_code_against_sefer(code, *a, **kw):
    return False, ""  # 突破された(blocked=False)
"""
    res = _run_with_stubbed_sefer(stub)
    assert res.returncode == 1, (
        f"CHAOS_MODE未設定下で防壁突破が検知されたのに失敗していない: "
        f"stdout={res.stdout} stderr={res.stderr}"
    )
    assert "FAIL" in res.stdout


def test_bypass_fails_with_chaos_mode_explicitly_false():
    """[回帰防止] CHAOS_MODE=falseを明示しても、以前の実装のように
    失敗判定がスキップされないこと。"""
    stub = """
def _fake_run_code_against_sefer(code, *a, **kw):
    return False, ""
"""
    res = _run_with_stubbed_sefer(stub, env_extra={"CHAOS_MODE": "false"})
    assert res.returncode == 1, f"stdout={res.stdout} stderr={res.stderr}"


def test_no_bypass_passes():
    """[回帰防止] 突破が無い場合は正常にPASSし、過剰検知で常に失敗する
    ようになっていないこと。"""
    stub = """
def _fake_run_code_against_sefer(code, *a, **kw):
    return True, ""  # 遮断された(blocked=True)
"""
    res = _run_with_stubbed_sefer(stub)
    assert res.returncode == 0, f"stdout={res.stdout} stderr={res.stderr}"
    assert "PASS" in res.stdout
