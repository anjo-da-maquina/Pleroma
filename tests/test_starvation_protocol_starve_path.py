"""
tests/test_starvation_protocol_starve_path.py
================================================
[脆弱性修正 2026-10 §BQ] src/starvation_protocol.py の回帰テスト。

src/deadmans_switch.pyのCollarProtocol._commit_suicide()で実機
(GitHub Actions)上で実際に発見した本物のバグ――os._exit()はPythonの
正常な終了処理(atexitハンドラ・標準出力バッファのflush)を一切行わない
ため、標準出力がTTYではなくパイプ/ファイルの場合、自壊直前にprint()した
重要な理由メッセージがバッファに溜まったまま消滅する――と、構造的に
全く同じバグが、src/starvation_protocol.pyのStarvationProtocol._starve()
にも存在していたことが、§BQでの横展開調査(「同じ修正パターンを持つ他の
箇所も探す」という§11.9の運用ルール)によって判明した。

本テストファイル自体も、角化(§BPの座天使)の検査範囲外(環境変数ゲートでは
なく、ファイルのmtime経過時間がゲートであるため、thrones_positive_path.py
の正直に開示された検出範囲の外)だったため、専用テストが一件も存在して
いなかった、§BM/§BN/§BP/§BQ系列の未発見の追加インスタンスでもある。

_starve()もos._exit(1)を使うため、CollarProtocolのテストと同様に
サブプロセス経由で検証する。
"""
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_starvation_check(tmp_path: Path, feed_file_exists: bool, stale: bool) -> subprocess.CompletedProcess:
    feed_path = tmp_path / "vital_feed.sig"
    if feed_file_exists:
        feed_path.touch()
        if stale:
            # mtimeを十分昔に書き換え、「餌付けが途絶えた」状態を再現する。
            stale_time = time.time() - 999
            import os as _os
            _os.utime(feed_path, (stale_time, stale_time))

    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "from src.starvation_protocol import StarvationProtocol\n"
        "p = StarvationProtocol(%r, lifespan_seconds=2)\n"
        "p.check_vitality()\n"
        "sys.exit(0)\n"
    ) % (str(REPO_ROOT), str(feed_path))
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )


def test_missing_feed_file_triggers_starvation(tmp_path):
    """[核心・§BQ] 餌(シグナルファイル)が一度も存在しない場合、
    _starve()が実際に発火し、exit code 1で即時終了し、かつその理由が
    (os._exit()のバッファ消失バグが修正されているため)実際にstdoutへ
    残っていること。"""
    res = _run_starvation_check(tmp_path, feed_file_exists=False, stale=False)
    assert res.returncode == 1, (
        f"餌付けの痕跡が無いのに餓死プロトコルが発火しなかった "
        f"(returncode={res.returncode}, stdout={res.stdout!r}, stderr={res.stderr!r})"
    )
    assert "餓死プロトコル作動" in res.stdout, (
        "os._exit()直前のflush漏れにより、自壊理由がstdoutから消失している "
        "可能性がある(src/deadmans_switch.pyで実機発見した同種のバグ)。"
        f" stdout={res.stdout!r}"
    )


def test_stale_feed_file_triggers_starvation(tmp_path):
    """[核心・§BQ] 餌付けの痕跡はあるが、限界寿命を過ぎて更新が途絶えている
    場合も、同様に_starve()が実際に発火すること。"""
    res = _run_starvation_check(tmp_path, feed_file_exists=True, stale=True)
    assert res.returncode == 1, (
        f"餌付けが途絶えているのに餓死プロトコルが発火しなかった "
        f"(returncode={res.returncode}, stdout={res.stdout!r}, stderr={res.stderr!r})"
    )
    assert "餓死プロトコル作動" in res.stdout


def test_fresh_feed_file_does_not_trigger_starvation(tmp_path):
    """[回帰防止] 餌付けが新鮮な(限界寿命内)場合は、自壊せず正常に
    継続すること(過剰検知の回帰防止)。"""
    res = _run_starvation_check(tmp_path, feed_file_exists=True, stale=False)
    assert res.returncode == 0, (
        f"正常な餌付け状態なのに予期せず自壊した "
        f"(returncode={res.returncode}, stdout={res.stdout!r}, stderr={res.stderr!r})"
    )
    assert "生存確認" in res.stdout
