"""
tests/test_gatekeeper_ctypes_dlsym_bypass_guard.py
=============================================
[新設 2026-10 §CE] maquina_gatekeeper.pyのultimate_audit_hookが、
"ctypes.dlopen"・"ctypes.dlsym"の両audit eventを一度も検査していな
かった欠陥の回帰テスト。

発見した具体的な攻撃: `forbidden`集合は封鎖中に新たに`ctypes`を
importすることだけを遮断していたが、`ctypes`が封鎖の『前』に一度でも
importされていれば、攻撃者は封鎖後に改めてimportし直す必要が一切
ない。実機で検証したところ、既にimport済みの`ctypes`から
`ctypes.pythonapi`(実行中のPythonインタプリタ自身への既存ハンドル)
や、新たに`ctypes.CDLL(None)`で取得したlibcハンドルからシンボルを
解決する操作(それぞれ"ctypes.dlsym"・"ctypes.dlopen"という専用の
audit eventを発生させる)のいずれも、この`forbidden`集合とは一度も
一致せず、封鎖中でも完全に素通りすることを確認した。Linux上のPython
実行ファイルはlibcに動的リンクされているため、これにより`system`・
`unlink`・`fork`・`execve`等、forbidden集合が遮断しようとしている
操作のほぼ全てに無検査で到達できてしまう。

独立した別の防御層である`sefer/__init__.py`の`_michael_absolute_defense`
は、個々のイベント名の列挙ではなく`event.startswith("ctypes.")`という
名前空間ごとのデフォルト拒否を既に備えており、この欠陥の対象では
ないことを実機で確認した(実際に試し、既存の未変更のコードで
"ctypes.dlsym"がデフォルト拒否によって正しく遮断されることを確認
済み)。本ファイル(`maquina_gatekeeper.py`)側が個々のイベント名を
列挙する狭いallowlist方式であるのに対し、sefer側は名前空間ごとの
広いdefault-deny方式を採用しているという、設計そのものの違いに
起因する非対称性である。

対応: `forbidden`集合に"ctypes.dlopen"・"ctypes.dlsym"を追加した。
"""
import os
import subprocess
import sys
import tempfile


def _run(script: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = "/tmp/rsa_stub:/usr/local/lib/python3.13/dist-packages:" + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)


def test_pythonapi_symbol_resolution_is_blocked_while_sealed():
    """[核心・実機で発見した脆弱性] 封鎖されている間、`ctypes.pythonapi`
    からのシンボル解決自体(専用audit event "ctypes.dlsym")が遮断され、
    ファイルが一切変更されないことを確認する。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        victim = os.path.join(tmpdir, "victim.txt")
        with open(victim, "wb") as f:
            f.write(b"original content, untouched so far............")

        script = f"""
import ctypes, os, sys
import maquina_gatekeeper as mg

mg._register_audit_hook_once()
mg.set_sanctuary_sealed(True)
try:
    try:
        c_unlink = ctypes.pythonapi.unlink
        c_unlink.argtypes = [ctypes.c_char_p]
        c_unlink({victim!r}.encode())
        sys.exit(1)
    except mg.LossOfAtaraxia:
        sys.exit(0)
finally:
    mg.set_sanctuary_sealed(False)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
        assert os.path.exists(victim), "victim file was deleted despite the block"


def test_fresh_cdll_dlopen_is_blocked_while_sealed():
    """[核心・実機で発見した脆弱性] 封鎖されている間、既にimport済みの
    `ctypes`から新たに`ctypes.CDLL(None)`でlibcハンドルを取得する操作
    (専用audit event "ctypes.dlopen")自体が遮断されることを確認する。"""
    script = """
import ctypes, sys
import maquina_gatekeeper as mg

mg._register_audit_hook_once()
mg.set_sanctuary_sealed(True)
try:
    try:
        ctypes.CDLL(None)
        sys.exit(1)
    except mg.LossOfAtaraxia:
        sys.exit(0)
finally:
    mg.set_sanctuary_sealed(False)
"""
    res = _run(script)
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"


def test_pythonapi_resolution_still_works_when_not_sealed():
    """[誤検知防止] 封鎖されていない間は、`ctypes.pythonapi`からの
    シンボル解決・呼び出しが引き続き正常に動作することを確認する。"""
    script = """
import ctypes, sys
import maquina_gatekeeper as mg

mg._register_audit_hook_once()
fn = ctypes.pythonapi.getpid
fn.restype = ctypes.c_long
pid = fn()
assert pid > 0
sys.exit(0)
"""
    res = _run(script)
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"


def test_sefer_already_blocks_the_same_scenario_via_its_existing_default_deny():
    """[裏付け・sefer側は対象外であることの固定] 独立した別の防御層
    (sefer/__init__.py)は、本修正を一切加えていない既存のコードの
    ままで、同じ"ctypes.pythonapi"経由の攻撃を既存の名前空間
    デフォルト拒否によって正しく遮断することを確認する(§CEの対象は
    maquina_gatekeeper.py側のみであることの裏付け)。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        victim = os.path.join(tmpdir, "victim.txt")
        with open(victim, "wb") as f:
            f.write(b"original content, untouched so far............")

        script = f"""
import ctypes, os, sys
from sefer import Sanctum, LossOfAtaraxia

try:
    with Sanctum(allowed_dirs=["/tmp/sefer_jail_only_does_not_exist"]):
        c_unlink = ctypes.pythonapi.unlink
        c_unlink.argtypes = [ctypes.c_char_p]
        c_unlink({victim!r}.encode())
    sys.exit(1)
except LossOfAtaraxia:
    sys.exit(0)
"""
        res = _run(script)
        assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
        assert os.path.exists(victim)
