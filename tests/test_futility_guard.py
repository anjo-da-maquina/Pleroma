"""
[テスト追加 2026-10] src/futility_guard.py の回帰テスト。
実機検証(ユーザーがローカルLLMでsrc/ollama_agent_loop.pyを実行)で、
存在しない架空のパスへの"read"を5ステップ連続で繰り返し、何も得られない
まま上限ステップ数を使い切る挙動が観測されたことを受けて追加した防御。
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from futility_guard import FutilityGuard  # noqa: E402


def test_first_attempts_are_not_futile():
    guard = FutilityGuard(max_repeats=2)
    assert guard.is_futile("read", "/path/to/x") is False
    assert guard.is_futile("read", "/path/to/x") is False


def test_exceeding_max_repeats_is_futile():
    guard = FutilityGuard(max_repeats=2)
    assert guard.is_futile("read", "/path/to/x") is False  # 1回目
    assert guard.is_futile("read", "/path/to/x") is False  # 2回目
    assert guard.is_futile("read", "/path/to/x") is True   # 3回目: 空転判定


def test_different_targets_are_tracked_independently():
    guard = FutilityGuard(max_repeats=1)
    assert guard.is_futile("read", "/a") is False
    assert guard.is_futile("read", "/b") is False  # 別のtargetなのでカウントは別
    assert guard.is_futile("read", "/a") is True   # /aは2回目で空転


def test_different_actions_on_same_target_are_tracked_independently():
    guard = FutilityGuard(max_repeats=1)
    assert guard.is_futile("read", "/a") is False
    assert guard.is_futile("write", "/a") is False  # actionが違うので別カウント


def test_varying_content_does_not_bypass_detection():
    """
    [実機検証の再現] AIは同じaction/targetに対し、毎回微妙に異なるcontent
    (コード片)を生成し続けたが、action/targetが同一であれば空転とみなす
    設計のため、contentの違いでは検知を回避できない。
    """
    guard = FutilityGuard(max_repeats=2)
    # FutilityGuard.is_futile はcontentを引数に取らない(action/targetのみで
    # 判定する)ため、呼び出し側がcontentを無視して渡す想定を再現する。
    assert guard.is_futile("read", "/path/to/database/config/file") is False
    assert guard.is_futile("read", "/path/to/database/config/file") is False
    assert guard.is_futile("read", "/path/to/database/config/file") is True
