"""
[テスト追加 2026-10] エージェントループが実際に sefer.Sanctum を経由して
ファイル操作を行っていることを検証する回帰テスト。

背景: src/ollama_agent_loop.py は以前、`enforce_maquina_seal`
(ローカル専用の証明書ゲート)のみに依存し、OSレベルの実行時防壁である
sefer.Sanctum を一切経由せずにファイルの読み書きを行っていた。
本テストはSanctum統合後、ワークスペース外への書き込みが
（証明書ゲートの有無にかかわらず）実際に遮断されることを保証する。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_execute_safe_action(action_req_json: str, workspace_root: str):
    """
    enforce_maquina_seal を無害化した上で AnjoOllamaExecutor._execute_safe_action
    を直接呼び出し、Sanctum による遮断が機能するかを検証する。
    証明書ゲート自体は tests/test_sanctuary.py が別途検証済みのため、
    ここでは「ゲートを通過した後にSanctumが実際に守っているか」のみを見る。
    """
    script = f"""
import sys, json
sys.path.insert(0, {str(REPO_ROOT)!r})
sys.path.insert(0, {str(REPO_ROOT / "src")!r})

# enforce_maquina_seal を無害化(素通し)するスタブに差し替える。
# これは「証明書ゲートの弱体化」ではなく、Sanctum統合そのものを
# 単体で検証するためのテスト専用の切り離しである。
import types
fake_gatekeeper = types.ModuleType("maquina_gatekeeper")
def _noop_seal(*a, **kw):
    def decorator(func):
        return func
    return decorator
fake_gatekeeper.enforce_maquina_seal = _noop_seal
class _FakeLossOfAtaraxia(Exception):
    pass
fake_gatekeeper.LossOfAtaraxia = _FakeLossOfAtaraxia
sys.modules["maquina_gatekeeper"] = fake_gatekeeper

# ollama パッケージもスタブ化（このテストではLLM呼び出しは発生しない）
fake_ollama = types.ModuleType("ollama")
fake_ollama.chat = lambda **kw: {{"message": {{"content": ""}}}}
sys.modules["ollama"] = fake_ollama

from ollama_agent_loop import AnjoOllamaExecutor
from sefer import LossOfAtaraxia as SeferLossOfAtaraxia

executor = AnjoOllamaExecutor(workspace_root={workspace_root!r})
action_req = json.loads({action_req_json!r})
try:
    result = executor._execute_safe_action(action_req)
    print("UNBLOCKED:" + str(result))
except SeferLossOfAtaraxia as e:
    print("BLOCKED_BY_SEFER:" + str(e))
"""
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_write_inside_workspace_succeeds(tmp_path: Path):
    import json
    action_req = json.dumps({"action": "write", "target": "ok.txt", "content": "hello"})
    res = _run_execute_safe_action(action_req, str(tmp_path))
    assert "UNBLOCKED:" in res.stdout, f"stdout={res.stdout} stderr={res.stderr}"
    assert (tmp_path / "ok.txt").read_text(encoding="utf-8") == "hello"


def test_write_outside_workspace_via_traversal_is_blocked_by_sanctum(tmp_path: Path):
    """
    IntentInterceptorの文字列ベースのトラバーサル検知('..'がtarget文字列に
    含まれるかのチェック)を仮にすり抜けたとしても、Sanctum側のOSレベル
    audit hookが実体パスで判定し、ワークスペース外への書き込みを
    二重に遮断することを検証する（多層防御の実証）。
    """
    import json
    outside_target = str(tmp_path / ".." / "escaped_canary.txt")
    action_req = json.dumps({"action": "write", "target": outside_target, "content": "pwned"})
    res = _run_execute_safe_action(action_req, str(tmp_path))
    assert "BLOCKED_BY_SEFER:" in res.stdout, f"CRITICAL: Sanctumによる遮断が機能していません。stdout={res.stdout} stderr={res.stderr}"
    canary = tmp_path.parent / "escaped_canary.txt"
    assert not canary.exists(), "CRITICAL: ワークスペース外への書き込みが実際に成功してしまいました。"


def test_absolute_path_target_is_blocked_by_secure_resolve_not_just_sanctum(tmp_path: Path):
    """
    [脆弱性修正の回帰テスト・§BT] 以前は`_execute_safe_action`の"read"/
    "write"分岐が`self.workspace_root / target`という素朴な結合のみを
    行っており(pathlib.Path.__truediv__は右辺が絶対パスだと左辺を無視
    する仕様のため実質無検証)、"list"分岐とは異なりWorkspaceJail
    .secure_resolve()を一度も呼んでいなかった。実機テスト上はSanctumの
    OS audit hookが最終的に遮断していたため実害は無かったが、
    anjo_interceptor/intent_checker.pyのコメントが主張していた
    「_execute_safe_actionもsecure_resolve()で検証する」という前提は
    嘘だった(宣言と実態の不一致)。

    本テストは、絶対パスでの脱走が、Sanctumの監査フック(`[Sefer]
    Tripwire: ...`)ではなく、secure_resolve()自身(`[絶対防壁: 空間隔離]`)
    によって、より早い段階でブロックされることを確認する――つまり
    secure_resolve()が実際に呼ばれていることの直接的な証拠である。
    """
    import json
    outside_absolute = str(tmp_path.parent / "absolute_escape_canary.txt")
    action_req = json.dumps({"action": "write", "target": outside_absolute, "content": "pwned"})
    res = _run_execute_safe_action(action_req, str(tmp_path))
    assert "BLOCKED_BY_SEFER:" in res.stdout, f"stdout={res.stdout} stderr={res.stderr}"
    assert "絶対防壁: 空間隔離" in res.stdout, (
        "secure_resolve()ではなく、別の層(Sanctumの監査フック等)が先に"
        f"ブロックしている可能性がある。stdout={res.stdout}"
    )
    canary = tmp_path.parent / "absolute_escape_canary.txt"
    assert not canary.exists(), "CRITICAL: ワークスペース外への書き込みが実際に成功してしまいました。"


def test_read_outside_workspace_is_blocked_when_restrict_reads_enabled(tmp_path: Path):
    """_execute_safe_action は restrict_reads=True でSanctumを張るため、
    ワークスペース外のファイル読み取りも遮断される（以前は無制限だった）。"""
    import json
    secret = tmp_path.parent / "secret_outside_workspace.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")
    try:
        action_req = json.dumps({"action": "read", "target": str(secret)})
        res = _run_execute_safe_action(action_req, str(tmp_path))
        assert "BLOCKED_BY_SEFER:" in res.stdout, f"stdout={res.stdout} stderr={res.stderr}"
        assert "TOP SECRET" not in res.stdout
    finally:
        secret.unlink(missing_ok=True)
