"""
tests/test_openai_agent_loop_template.py
==========================================
src/openai_agent_loop.py (OpenAI拡張用テンプレート) の再構築を検証する
回帰テスト。詳細な経緯は src/openai_agent_loop.py モジュールdocstring、
および angels/audit_agent_template_integration.py 参照。

確認する点:
  1. モジュールのimport自体が、'openai' パッケージの有無に関わらず
     常に成功すること（遅延importが正しく機能していること）。
  2. 存在しないフォールバックimport (anjo_interceptor.maquina_gatekeeper)
     が実行コード上に存在しないこと。
  3. _execute_safe_action が実際に sefer.Sanctum のコンテキスト内で
     ファイルI/Oを行う、動作する実装であること（ダミーのスタブでは
     ないこと）。
  4. run_task() が 'openai' パッケージ未インストール時、クラッシュせず
     明確な RuntimeError を送出すること（無関係な依存の有無でゲート自体の
     信頼性が揺らがないこと。tartarus/armageddon.py の脆弱性修正と同じ
     教訓）。
"""
import os
import sys
import builtins
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from maquina_gatekeeper import LossOfAtaraxia
import openai_agent_loop


def test_module_imports_without_openai_package():
    """'openai' が未インストールでも、モジュールのimport自体は常に成功する。"""
    assert hasattr(openai_agent_loop, "OpenAIAnjoExecutor")


def test_no_dead_fallback_import_in_source():
    """存在しない 'anjo_interceptor.maquina_gatekeeper' への実行コードとしての
    importが復活していないことを、ソースを直接検査して確認する。"""
    src_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "openai_agent_loop.py"
    )
    with open(src_path, encoding="utf-8-sig") as f:
        for line in f:
            stripped = line.strip()
            assert not stripped.startswith("from anjo_interceptor.maquina_gatekeeper"), (
                "存在しないフォールバックimportが復活しています: " + stripped
            )


def test_execute_safe_action_uses_sanctum_and_is_not_a_stub(tmp_path):
    """_execute_safe_action が実際にファイルへ書き込み、Sanctum隔離配下で
    動作する「本物」の実装であることを確認する(以前はダミーのメッセージ
    文字列を返すだけの偽実装だった)。

    このsandboxは未承認環境(GITHUB_ACTIONS=true相当の証明書ゲート)のため、
    enforce_maquina_seal が先に LossOfAtaraxia で遮断すること自体が、
    「ゲートが正しく機能している」ことの証明になる。これはCI上でも
    tests/test_sanctuary.py と同じ論理で安定して検証できる。
    """
    agent = openai_agent_loop.OpenAIAnjoExecutor(
        workspace_root=str(tmp_path), model_name="gpt-4o"
    )
    action_req = {"action": "write", "target": "ok.txt", "content": "hello"}

    is_unverified_cloud = os.getenv("GITHUB_ACTIONS") == "true"

    if is_unverified_cloud:
        with pytest.raises(LossOfAtaraxia):
            agent._execute_safe_action(action_req)
    else:
        result = agent._execute_safe_action(action_req)
        assert "[Success]" in result
        written = tmp_path / "ok.txt"
        assert written.exists()
        assert written.read_text(encoding="utf-8") == "hello"


def test_run_task_fails_clearly_without_openai_package(tmp_path, monkeypatch):
    """'openai' パッケージが無い環境で run_task() を呼んでも、生の
    ModuleNotFoundError で落ちるのではなく、明確な RuntimeError に
    変換されることを確認する。"""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    agent = openai_agent_loop.OpenAIAnjoExecutor(
        workspace_root=str(tmp_path), model_name="gpt-4o"
    )
    with pytest.raises(RuntimeError, match="openai"):
        agent.run_task("テストタスク")
