"""
tests/test_thrones_positive_path.py
=====================================
[新設 2026-10 §BP] angels/thrones_positive_path.py の単体テスト。

本天使は、§BM(CHAOS_MODE)・§BN(HMAC連鎖)・§BP(shamir_seal.py・
deadmans_switch.py)で実際に見つかった「環境変数ゲート付きの重要分岐に、
有効側を踏むテストが無い」という共通パターンを、一般化して機械的に
検知するためのヒューリスティックな静的解析である。

本テストは、(1) 基本的な検知能力、(2) 実装中に自己発見した誤検知
(コメント内の例示コードを本物のゲートと誤認識する)の回帰防止、
(3) 既知の検知限界(間接呼び出しによる回避)を、実機の挙動として固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import thrones_positive_path as tpp


def test_detects_direct_conditional_gate():
    """os.getenv(...)を直接if文の条件式に書く形を検知する。"""
    text = 'if os.getenv("MY_FLAG") == "true":\n    pass\n'
    assert tpp.find_env_gated_vars(text) == {"MY_FLAG": True}


def test_detects_variable_assigned_then_gated():
    """変数に代入してから、その変数をif文のゲートに使う形を検知する。"""
    text = 'x = os.getenv("MY_FLAG")\nif x:\n    pass\n'
    assert tpp.find_env_gated_vars(text) == {"MY_FLAG": True}


def test_detects_environ_get_form():
    """os.environ.get(...)形式も検知する。"""
    text = 'y = os.environ.get("MY_FLAG")\nif y:\n    pass\n'
    assert tpp.find_env_gated_vars(text) == {"MY_FLAG": True}


def test_detects_environ_subscript_form():
    """[レッドチームで発見・即時修正] os.environ["X"]の添字アクセス形式も
    検知する(当初の実装はos.getenv/os.environ.getのみ対応しており、
    この形式は回避できてしまっていた)。"""
    text = 'z = os.environ["MY_FLAG"]\nif z == "bypass":\n    pass\n'
    assert tpp.find_env_gated_vars(text) == {"MY_FLAG": True}


def test_does_not_flag_variable_only_used_for_logging():
    """制御フロー(if文)に一切使われず、ログ出力等にのみ使われる変数は
    ゲートとして誤検知しない。"""
    text = 'v = os.getenv("JUST_FOR_LOGGING")\nprint(v)\n'
    assert tpp.find_env_gated_vars(text) == {}


def test_does_not_flag_example_code_inside_comments():
    """[核心・実装中の自己発見] 説明用コメント内に書かれた例示コード
    (`os.getenv("X")`等)を、本物の環境変数ゲートとして誤検知しない
    (角度検出中に自分自身のソースコードに対して実行し、実際にこの
    誤検知を起こしたことを修正した回帰防止テスト)。"""
    text = (
        '# 例: `if os.getenv("X") == "true":`のような形を検知する\n'
        'print("no real gate here")\n'
    )
    assert tpp.find_env_gated_vars(text) == {}


def test_known_limitation_indirect_wrapper_call_is_not_detected():
    """[正直な既知の限界の固定] os.getenvをラップした間接呼び出し経由の
    ゲートは、本ヒューリスティックでは検知できない(§11.9フェーズFの
    一般形)。これは「直せていない」ことを隠さず、実機の挙動として
    明示的に固定しておくための回帰テストである。"""
    text = (
        'def _get(name):\n'
        '    return os.getenv(name)\n'
        'flag = _get("MY_FLAG")\n'
        'if flag:\n'
        '    pass\n'
    )
    assert tpp.find_env_gated_vars(text) == {}, (
        "既知の限界が予期せず解消されている場合はこのテストを更新すること"
    )


def test_known_non_gating_vars_are_excluded_even_when_gated():
    """KNOWN_NON_GATING_VARSに含まれる変数は、たとえ条件分岐に使われて
    いても除外対象とする(誤検知を避けるための明示的な許可リスト)。"""
    text = 'if os.getenv("GITHUB_RUN_ID"):\n    pass\n'
    assert tpp.find_env_gated_vars(text) == {}
