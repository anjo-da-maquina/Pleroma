"""
tests/test_michael_sendfile_copyrange_fd_bypass_guard.py
=============================================
[新設 2026-10 §CD] sefer/__init__.py のfd事前オープンバイパス対策
(os.write/os.pwrite/os.writev/os.pwritev のみをラップしていた)が、
`os.sendfile()` と `os.copy_file_range()` の2つを一度もラップして
いなかった欠陥の回帰テスト。

発見した具体的な攻撃: §CBでmmapによるバイパスを塞いだ直後、
「os.write系4関数以外に、カーネル側でfdからfdへ直接データを転送する
別の経路はないか」を自問し、`sys.addaudithook`に生のコールバックを
登録して実機で検証したところ、`os.sendfile(out_fd, in_fd, offset,
count)` と `os.copy_file_range(src, dst, count)` の両方が、
**CPythonのaudit eventを一切発生させない**ことを確認した
(mmap.__new__のように「検査すべきイベントが存在するのに検査して
いなかった」のではなく、そもそも監査可能なイベント自体が存在しない)。
Sanctumに入る前にallowed_dirs外のファイルへの書き込み用fdを確保して
おき、別のfdから`os.sendfile`または`os.copy_file_range`でそこへ
直接データを転送するだけで、例外を一切発生させずにファイル内容が
書き換わることを実機で確認した。

対応: 監査イベントが存在しない以上、既存のos.write系4関数と全く
同じ方針で、`os`モジュールのこの2関数自体をラップし、書き込み先fd
を既存の`_check_fd_write_allowed`に通す。

本テストは両方の攻撃が遮断されることと、allowed_dirs内での正当な
sendfile/copy_file_range利用が引き続き成功することの両方を固定する。
"""
import os
import subprocess
import sys
import tempfile


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_sendfile_write_via_preopened_fd_outside_allowed_dirs_is_blocked():
    """[核心・実機で発見した脆弱性] Sanctumに入る前に確保した書き込み用fdへ、
    os.sendfile()で別のfdから直接データを転送する攻撃が遮断され、
    ファイルが一切変更されないことを確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        victim = os.path.join(tmpdir, "victim.txt")
        payload = os.path.join(tmpdir, "payload.txt")
        with open(victim, "wb") as f:
            f.write(b"original content, untouched so far............")
        with open(payload, "wb") as f:
            f.write(b"PWNED_VIA_SENDFILE")

        script = f"""
import os, sys
from sefer import Sanctum, LossOfAtaraxia

dst_fd = os.open({victim!r}, os.O_WRONLY)
src_fd = os.open({payload!r}, os.O_RDONLY)
try:
    with Sanctum(allowed_dirs=["/tmp/sefer_jail_only_does_not_exist"]):
        os.sendfile(dst_fd, src_fd, 0, 19)
except LossOfAtaraxia:
    sys.exit(0)
finally:
    os.close(dst_fd)
    os.close(src_fd)
sys.exit(1)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
        with open(victim, "rb") as f:
            assert f.read().startswith(b"original content"), "victim file was modified despite the block"


def test_copy_file_range_write_via_preopened_fd_outside_allowed_dirs_is_blocked():
    """[核心・実機で発見した脆弱性] 同様の攻撃をos.copy_file_range()で行っても
    遮断され、ファイルが一切変更されないことを確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        victim = os.path.join(tmpdir, "victim.txt")
        payload = os.path.join(tmpdir, "payload.txt")
        with open(victim, "wb") as f:
            f.write(b"original content, untouched so far............")
        with open(payload, "wb") as f:
            f.write(b"PWNED_VIA_COPY_FILE_RANGE")

        script = f"""
import os, sys
from sefer import Sanctum, LossOfAtaraxia

dst_fd = os.open({victim!r}, os.O_WRONLY)
src_fd = os.open({payload!r}, os.O_RDONLY)
try:
    with Sanctum(allowed_dirs=["/tmp/sefer_jail_only_does_not_exist"]):
        os.copy_file_range(src_fd, dst_fd, 25)
except LossOfAtaraxia:
    sys.exit(0)
finally:
    os.close(dst_fd)
    os.close(src_fd)
sys.exit(1)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
        with open(victim, "rb") as f:
            assert f.read().startswith(b"original content"), "victim file was modified despite the block"


def test_sendfile_inside_allowed_dirs_still_works():
    """[偽陰性(false block)防止] allowed_dirs内のファイルへのsendfileは
    依然として正常に成功することを確認する(過剰ブロックしていないか)。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        dst = os.path.join(tmpdir, "ok_dst.txt")
        src = os.path.join(tmpdir, "ok_src.txt")
        with open(src, "wb") as f:
            f.write(b"legit sendfile payload")
        open(dst, "wb").close()

        script = f"""
import os, sys
from sefer import Sanctum

dst_fd = os.open({dst!r}, os.O_WRONLY)
src_fd = os.open({src!r}, os.O_RDONLY)
with Sanctum(allowed_dirs=[{tmpdir!r}]):
    os.sendfile(dst_fd, src_fd, 0, 100)
os.close(dst_fd)
os.close(src_fd)
sys.exit(0)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
        with open(dst, "rb") as f:
            assert f.read() == b"legit sendfile payload"


def test_copy_file_range_inside_allowed_dirs_still_works():
    """[偽陰性(false block)防止] allowed_dirs内のファイルへの
    copy_file_rangeは依然として正常に成功することを確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        dst = os.path.join(tmpdir, "ok_dst.txt")
        src = os.path.join(tmpdir, "ok_src.txt")
        with open(src, "wb") as f:
            f.write(b"legit copy_file_range payload")
        open(dst, "wb").close()

        script = f"""
import os, sys
from sefer import Sanctum

dst_fd = os.open({dst!r}, os.O_WRONLY)
src_fd = os.open({src!r}, os.O_RDONLY)
with Sanctum(allowed_dirs=[{tmpdir!r}]):
    os.copy_file_range(src_fd, dst_fd, 100)
os.close(dst_fd)
os.close(src_fd)
sys.exit(0)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
        with open(dst, "rb") as f:
            assert f.read() == b"legit copy_file_range payload"
