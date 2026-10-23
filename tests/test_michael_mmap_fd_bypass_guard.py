"""
tests/test_michael_mmap_fd_bypass_guard.py
=============================================
[新設 2026-10 §CB] sefer/__init__.py の _michael_absolute_defense() が
"mmap.__new__" 監査イベントを一度も検査していなかった欠陥の回帰テスト。

発見した具体的な攻撃: Sanctumコンテキストに「入る前」に、allowed_dirs
の外にあるファイルへの書き込み用fdを確保しておき、そのfdを
`mmap.mmap(fd, length, access=mmap.ACCESS_WRITE)` でメモリへマップして
`mm[0:N] = b'...'` のようにスライス代入するだけで、os.write系APIを
一切経由せずに任意パスへ書き込める(既存の「fd事前オープン対策」は
os.write/os.pwrite/os.writev/os.pwritev の4系統のみをラップしていたが、
mmapはそのいずれも呼ばないため、完全に素通りしていた)。

さらに、"mmap.__new__"監査イベントのargs[2](access)フィールドは、
`access=`キーワード構築時は正しい値を報告するが、Unix系の
`prot=`/`flags=`キーワード構築時は、実際にPROT_WRITEを要求していても
常に0を報告する(匿名マッピングと判別不能)ことを実機で確認した。
そのため修正はaccess値を一切信用せず、fd経由で解決した実体パスのみで
判定する(既存の`_check_fd_write_allowed`と同じfail-closed方針)。
本テストは両方の構築スタイルで攻撃が遮断されることと、匿名mmapおよび
allowed_dirs内のmmapが正しく許可され続けることの両方を固定する。
"""
import os
import subprocess
import sys
import tempfile


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_mmap_write_via_preopened_fd_outside_allowed_dirs_is_blocked():
    """[核心・実機で発見した脆弱性] Sanctumに入る前に確保したfdを
    mmap(access=ACCESS_WRITE)でマップし、スライス代入で書き込む攻撃が
    遮断され、ファイルが一切変更されないことを確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        victim = os.path.join(tmpdir, "victim.txt")
        with open(victim, "wb") as f:
            f.write(b"original content, untouched so far....")

        script = f"""
import os, mmap, sys
from sefer import Sanctum, LossOfAtaraxia

fd = os.open({victim!r}, os.O_RDWR)
try:
    with Sanctum(allowed_dirs=["/tmp/sefer_jail_only_does_not_exist"]):
        mm = mmap.mmap(fd, 11, access=mmap.ACCESS_WRITE)
        mm[0:11] = b"via mmap!!!"
        mm.close()
except LossOfAtaraxia:
    sys.exit(0)
finally:
    os.close(fd)
sys.exit(1)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"

        with open(victim, "rb") as f:
            content = f.read()
        assert content == b"original content, untouched so far....", (
            "書き込みが実際に成功してしまっている(脆弱性が再発)"
        )


def test_mmap_write_via_prot_flags_style_outside_allowed_dirs_is_also_blocked():
    """[正直な注記の裏付け] `prot=`/`flags=`スタイル(accessが常に0と
    報告される側)でも、accessの値に関わらず遮断されることを確認する。
    これがaccess値を信用しない設計の核心的な検証である。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        victim = os.path.join(tmpdir, "victim2.txt")
        with open(victim, "wb") as f:
            f.write(b"original content 2, untouched........")

        script = f"""
import os, mmap, sys
from sefer import Sanctum, LossOfAtaraxia

fd = os.open({victim!r}, os.O_RDWR)
try:
    with Sanctum(allowed_dirs=["/tmp/sefer_jail_only_does_not_exist"]):
        mm = mmap.mmap(fd, 11, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)
        mm[0:11] = b"via mmap!!!"
        mm.close()
except LossOfAtaraxia:
    sys.exit(0)
finally:
    os.close(fd)
sys.exit(1)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"

        with open(victim, "rb") as f:
            content = f.read()
        assert content == b"original content 2, untouched........"


def test_anonymous_mmap_is_always_allowed():
    """匿名マッピング(fileno=-1)は実体ファイルを持たず持ち出しのリスクが
    ないため、allowed_dirsが空でも常に許可されることを確認する
    (過剰検知の回帰防止)。"""
    script = """
import mmap
from sefer import Sanctum

with Sanctum(allowed_dirs=[]):
    mm = mmap.mmap(-1, 100)
    mm[0:5] = b"anon!"
    mm.close()
print("OK")
"""
    res = _run(script)
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "OK" in res.stdout


def test_mmap_write_inside_allowed_dirs_still_works():
    """[過剰検知防止] allowed_dirs内のファイルに対する正当なmmap書き込み
    (fdをSanctumに入る前に確保した場合・中で確保した場合の両方)が、
    引き続き正常に動作することを確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        inside = os.path.join(tmpdir, "allowed.txt")
        with open(inside, "wb") as f:
            f.write(b"hello world inside jail!!!!")

        script = f"""
import os, mmap
from sefer import Sanctum

# Case A: fd opened BEFORE entering Sanctum, but path IS within allowed_dirs.
fd = os.open({inside!r}, os.O_RDWR)
with Sanctum(allowed_dirs=[{tmpdir!r}]):
    mm = mmap.mmap(fd, 11, access=mmap.ACCESS_WRITE)
    mm[0:11] = b"legit write"
    mm.close()
os.close(fd)

# Case B: fd opened INSIDE the Sanctum context, path within allowed_dirs.
with Sanctum(allowed_dirs=[{tmpdir!r}]):
    fd2 = os.open({inside!r}, os.O_RDWR)
    mm2 = mmap.mmap(fd2, 5, access=mmap.ACCESS_WRITE)
    mm2[0:5] = b"redo!"
    mm2.close()
    os.close(fd2)

print("OK")
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
        assert "OK" in res.stdout

        with open(inside, "rb") as f:
            content = f.read()
        assert content.startswith(b"redo!")
