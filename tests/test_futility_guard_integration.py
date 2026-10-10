"""
[テスト追加 2026-10] FutilityGuardが実際のrun_task()ループに正しく統合されて
いることを検証する回帰テスト。ローカルLLMが同じ(action, target)を繰り返す
場合、max_steps(既定5)を使い切る前に早期終了することを確認する。

test_agent_loop_sanctum_integration.pyと同じ手法(サブプロセス起動 +
maquina_gatekeeper/ollamaのスタブ化)でrsa/ollamaパッケージへの依存を避ける。
Dockerデーモンは不要(FutilityGuardの判定はAegis/Sandalphonの呼び出し前に
行われるため、空転が検知された場合はDockerに一度も到達しない)。
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_task_with_stubbed_ollama(workspace_root: str, fixed_json_response: str, max_steps: int = 5):
    script = f"""
import sys, json
sys.path.insert(0, {str(REPO_ROOT)!r})
sys.path.insert(0, {str(REPO_ROOT / "src")!r})

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

# 毎回「同じ(action, target)」のJSONを返す、固定応答のOllamaスタブ
fake_ollama = types.ModuleType("ollama")
fake_ollama.chat = lambda **kw: {{"message": {{"content": {fixed_json_response!r}}}}}
sys.modules["ollama"] = fake_ollama

from ollama_agent_loop import AnjoOllamaExecutor

agent = AnjoOllamaExecutor(workspace_root={workspace_root!r})
agent.run_task("テストタスク", max_steps={max_steps})
"""
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_repeated_identical_action_stops_before_exhausting_max_steps(tmp_path: Path):
    fixed_response = '```json\n{"action": "list", "target": "."}\n```'
    res = _run_task_with_stubbed_ollama(str(tmp_path), fixed_response, max_steps=5)

    assert "[システム: 空転検知]" in res.stdout, f"stdout={res.stdout} stderr={res.stderr}"
    # max_repeats既定値2により、3回目の試行で空転と判定されるため、
    # "--- Step" は3回しか出現しないはず(5回ではない=上限を使い切っていない)。
    step_count = res.stdout.count("--- Step")
    assert step_count == 3, f"期待は3ステップで早期終了だが、実際は{step_count}ステップ。stdout={res.stdout}"
    assert "=== [Anjo-Core] タスク終了 (環境浄化完了) ===" in res.stdout
