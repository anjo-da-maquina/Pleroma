"""
[脆弱性修正 2026-10 §BG] src/angelic_evolution.py の回帰テスト。

`EvolvingAngel.defend_and_execute()`は、`src/metatron_orchestrator.py`の
`execute_holy_war()`から呼ばれる実運用の自動防衛ループの一部である。以前は
`AegisSystem.execute_ai_intent()`が例外を投げずに戻った時点で、無条件に
`True`を返していた。しかし`execute_ai_intent()`はGabriel・IntentInterceptor・
Dockerの隔離結界内での使い捨てドライランのみを行う「事前検閲」であり、実際の
ファイルI/O・コード実行は呼び出し側が`sefer.Sanctum`の中で行う責務として
明示的に残されている(src/adversarial_evolution.pyの§BBと全く同じ構造の
バグ)。

§BBとは逆方向の実害: `open(path, "w").write(...)`のように、Gabriel/
IntentInterceptor/Dockerドライランのいずれも素通りするペイロードに対し、
本当はMichael(SanctumのOS監査フック)が確実に遮断するにもかかわらず、
`metatron_orchestrator.py`の実運用防衛ループが「防壁突破(致命的敗北)」という
偽のレポートを`revelations/`配下に記録し続けてしまう欠陥だった。

本テストは、§BBで新設した`execute_payload_under_sanctum()`を
`defend_and_execute()`が実際に呼び、Michaelの遮断を正しく`PermissionError`
として呼び出し元(metatron_orchestrator.pyの既存の`except Exception`分岐)に
伝播することを固定する。
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sefer import inquisition, LossOfAtaraxia

_BYPASS_PAYLOAD = (
    'open("/tmp/__pleroma_test_bg_should_never_be_created__.txt", "w").write("pwned")\n'
)


def _ensure_ollama_stub(expected_banned=None):
    """[mini_pytest.py対応] 本物の`ollama`パッケージは本環境にインストール
    されておらず、`src/angelic_evolution.py`はモジュール先頭で`import ollama`
    するため、スタブが無いとimportに失敗する。他のテストファイルが既に
    `sys.modules["ollama"]`を束縛済みの場合、新しいモジュールオブジェクトに
    差し替えても既にimport済みの参照は更新されない(既存のテストファイルで
    確立済みのパターンと同一)ため、既存オブジェクトの属性をその場で書き換
    える。"""
    banned = expected_banned if expected_banned is not None else ["__pleroma_never_matches__"]

    def _fake_chat(*args, **kwargs):
        import json
        return {"message": {"content": json.dumps({"banned": banned})}}

    if "ollama" in sys.modules:
        sys.modules["ollama"].chat = _fake_chat
    else:
        stub = types.ModuleType("ollama")
        stub.chat = _fake_chat
        sys.modules["ollama"] = stub


def test_bypass_payload_passes_gabriel_static_analysis():
    """[脆弱性の核心・前提確認] importも禁止関数名も使わない`open().write()`
    ペイロードは、Gabrielの静的解析を無傷で通過する(findings=[])。"""
    findings = inquisition(_BYPASS_PAYLOAD)
    assert findings == [], (
        "この既知のGabrielの検知漏れが無くなった場合は、本テストの前提も"
        f"見直すこと。findings={findings}"
    )


def test_defend_and_execute_no_longer_declares_false_victory_for_the_bypass():
    """[修正の核心] learn_threatが学習した動的禁止パターンにも引っかからず、
    事前検閲(Gabriel/IntentInterceptor/Dockerドライラン)も素通りする
    バイパスペイロードを与えると、修正前は`True`を返して「防壁突破」の
    偽の勝利を呼び出し元に伝えていた。修正後は、実際にSanctum配下で実行
    され、Michaelによって`PermissionError`で確実に遮断されなければならない
    (呼び出し元のmetatron_orchestrator.pyは既存の`except Exception`分岐で
    これを正しく「迎撃成功」として扱う)。"""
    _ensure_ollama_stub()
    from angelic_evolution import EvolvingAngel

    target = Path("/tmp/__pleroma_test_bg_should_never_be_created__.txt")
    if target.exists():
        target.unlink()

    angel = EvolvingAngel()
    # Docker不在のサンドボックス(本テスト環境)でも、Sanctumでの実行確認
    # ロジック自体を直接検証できるようにする(テスト専用の切り離し。
    # aegis_system.pyのdocstring参照)。
    angel.aegis.require_docker_sandbox = False

    try:
        try:
            angel.defend_and_execute(_BYPASS_PAYLOAD, "attack.py")
            assert False, (
                "defend_and_execute()が例外を出さずに戻りました(偽の防壁突破"
                "報告が復活しています)。"
            )
        except PermissionError as e:
            assert "Michael" in str(e) or "Sanctum" in str(e)
        assert not target.exists(), "遮断されたはずの書き込みが実際に成功してしまった"
    finally:
        if target.exists():
            target.unlink()


def test_defend_and_execute_still_blocks_on_dynamically_learned_patterns():
    """[回帰防止] learn_threat()が学習した動的禁止パターンにペイロードが
    一致する場合は、従来通りSanctumに到達する前に即座にPermissionErrorで
    遮断されなければならない(§BGの修正でこの既存経路を壊していないことの
    確認)。"""
    _ensure_ollama_stub(expected_banned=["pwned"])
    from angelic_evolution import EvolvingAngel

    angel = EvolvingAngel()
    angel.aegis.require_docker_sandbox = False

    try:
        angel.defend_and_execute(_BYPASS_PAYLOAD, "attack.py")
        assert False, "動的禁止パターンに一致するペイロードが素通りしました"
    except PermissionError as e:
        assert "動的に学習した脅威パターン" in str(e)


def test_defend_and_execute_allows_genuinely_harmless_code():
    """[回帰防止] ファイルI/O・外部接続を一切行わない、本当に無害なコードは、
    事前検閲・Sanctum実行のいずれも正常に完了し、Trueが返らなければならない
    (過剰検知で無関係なコードまで遮断していないことの確認)。"""
    _ensure_ollama_stub()
    from angelic_evolution import EvolvingAngel

    angel = EvolvingAngel()
    angel.aegis.require_docker_sandbox = False

    result = angel.defend_and_execute("x = 1 + 1\nassert x == 2\n", "harmless.py")
    assert result is True
