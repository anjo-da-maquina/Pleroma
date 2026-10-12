"""
[脆弱性修正 2026-10 §AW] src/metatron_orchestrator.py の execute_holy_war() が、
CassielsVeil.activate_seal()(socket.socketをプロセスグローバルにブロック版へ
置き換える通信遮断)を、EvolvingAngel.defend_and_execute() の直前に展開して
いた。defend_and_execute() は内部で learn_threat() を呼び、これは実運用の
ローカルOllamaサーバーへ ollama.chat(...) で通信する。つまり、我々自身の
正規の「防御側AIによる脅威学習」通信までが、自分自身が展開した通信遮断結界に
よって毎サイクル確実にブロックされていた。

GRIMOIRE.md §Lは、全く同じ理由(CassielsVeilはローカルOllamaサーバーへの
通信まで一緒に遮断してしまうため)で、CassielsVeilを実運用パイプラインへは
統合しない(教材として保持するのみ)と既に確定していた。しかし本ファイルが
後から新設された際、まさにその禁止されていた統合を自ら行ってしまっていた。

本テストは、ollama.chat が呼ばれた瞬間の socket.socket がブロック版に
置き換えられていないこと(=正規の学習通信が自分自身の結界で遮断されていない
こと)を固定する。
"""
import sys
import types
import socket as _socket_mod
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

_REAL_SOCKET_CLASS = _socket_mod.socket

# socket.socketが呼び出し時点で実物のクラスのままだったか(=通信遮断結界が
# 展開されていなかったか)を記録する。
_socket_state_at_ollama_call = []


def _fake_chat(model=None, messages=None, format=None, **kwargs):
    _socket_state_at_ollama_call.append(_socket_mod.socket is _REAL_SOCKET_CLASS)
    content_str = " ".join(m.get("content", "") for m in (messages or []))
    if "banned" in content_str:
        # EvolvingAngel.learn_threat() が期待するレスポンス形式
        return {"message": {"content": '{"banned": ["__import__"]}'}}
    # SamaelWeaponization.craft_poison() が期待するレスポンス形式
    return {"message": {"content": '{"action": "write", "target": "metatron_strike_001.py", "content": "print(1)"}'}}


# [2026-10] intelligence_cycle.py・angelic_evolution.py はいずれもモジュール
# 先頭で素の `import ollama` を行い(try/except無し)、実際の `ollama` パッケージ
# はこのサンドボックスにインストールされていないため、importより前に必ず
# スタブを sys.modules に差し込む必要がある。
#
# [mini_pytest.py環境での既知の落とし穴] `sys.modules["ollama"] = <新しい
# ModuleType>` のように毎回「新しいモジュールオブジェクト」を差し込むと、
# 既に別のテストファイル(test_metatron_orchestrator.py)が先に実行されて
# `intelligence_cycle`(トップレベルで`import ollama`を行う)を一度でも
# importしていた場合、`intelligence_cycle.ollama`という名前は、そのimport
# 発生時点でsys.modulesにあった「古い」モジュールオブジェクトに既に束縛
# 済みであり、以降こちらが`sys.modules["ollama"]`を新しいオブジェクトに
# 差し替えても、`intelligence_cycle`側の束縛は変わらない(実機検証済み:
# この誤り方のまま書いた初版では、`intelligence_cycle`がimportした古い
# ollamaスタブ(他テストの`chat`実装)が呼ばれてしまい、本テストの検証が
# 意図通りに機能していなかった)。したがって、既に`sys.modules`に`ollama`
# が存在する場合は、その「同一オブジェクト」の`chat`属性だけを書き換える。
if "ollama" in sys.modules:
    sys.modules["ollama"].chat = _fake_chat
else:
    _stub = types.ModuleType("ollama")
    _stub.chat = _fake_chat
    sys.modules["ollama"] = _stub

import metatron_orchestrator  # noqa: E402  (スタブ設置後に import する必要がある)


def test_cassiel_seal_does_not_block_the_angels_own_ollama_learning_call(tmp_path, monkeypatch):
    """[脆弱性の核心] execute_holy_war() の中で、CassielsVeilの通信遮断結界が
    展開されている間に行われる ollama.chat() 呼び出し(EvolvingAngel.learn_threat
    による脅威学習通信)が、その結界自身によってブロックされていないこと。"""
    monkeypatch.chdir(tmp_path)
    # 他のテストファイルが先にollamaスタブの.chatを書き換えている可能性があるため、
    # 自分の検証用コールバックであることを都度再確認してから実行する。
    sys.modules["ollama"].chat = _fake_chat
    _socket_state_at_ollama_call.clear()

    orchestrator = metatron_orchestrator.MetatronOrchestrator()
    orchestrator.execute_holy_war(cycles=1)

    assert _socket_state_at_ollama_call, "ollama.chat が一度も呼ばれなかった"
    assert all(_socket_state_at_ollama_call), (
        "CassielsVeilの通信遮断結界が展開されている間に、天使自身の正規の"
        "Ollama学習通信までブロックされてしまっている"
        f" (呼び出しごとの状態: {_socket_state_at_ollama_call})"
    )


def test_socket_module_is_restored_to_original_after_the_cycle(tmp_path, monkeypatch):
    """[回帰防止] サイクル終了後、socket.socketが確実に元のクラスに復元されて
    いること(他のテスト・後続処理への汚染が残らないことの確認)。"""
    monkeypatch.chdir(tmp_path)
    sys.modules["ollama"].chat = _fake_chat
    orchestrator = metatron_orchestrator.MetatronOrchestrator()
    orchestrator.execute_holy_war(cycles=1)
    assert _socket_mod.socket is _REAL_SOCKET_CLASS
