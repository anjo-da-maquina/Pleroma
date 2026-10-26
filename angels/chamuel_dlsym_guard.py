import sys, os, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "シャムエルの影断ち (Chamuel's Shadow-Cut - ctypes.dlopen/dlsymによる深層保護の監査回避バイパス検知)"

# [新設 2026-10 §CE] 実際に発見した具体例: `maquina_gatekeeper.py`の
# `ultimate_audit_hook`は、`event == "import" and args[0] in
# {"ctypes", "_ctypes", "threading"}`で、封鎖中に新たに`ctypes`を
# importすること自体を遮断していた。しかし`ctypes`が封鎖の『前』に
# (本プロセス内の無関係な他のコードによってでも)一度でもimport
# されていれば、攻撃者は封鎖後に改めてimportし直す必要が一切ない。
# 実機で検証したところ、既にimport済みの`ctypes`から
# `ctypes.pythonapi`(`ctypes`自身がimport時に生成する、実行中の
# Pythonインタプリタ自身への既存ハンドル)や、新たに
# `ctypes.CDLL(None)`で取得したlibcハンドルからシンボルを解決する
# 操作(それぞれ"ctypes.dlsym"・"ctypes.dlopen"という専用のaudit
# eventを発生させる)のいずれも、`forbidden`集合とは一度も一致せず、
# 封鎖中でも完全に素通りすることを確認した。Linux上のPython実行
# ファイルはlibcに動的リンクされているため、これにより`system`・
# `unlink`・`fork`・`execve`等、forbidden集合が遮断しようとしている
# 操作のほぼ全てに、無検査で到達できてしまう。
#
# 独立した別の防御層である`sefer/__init__.py`の
# `_michael_absolute_defense`は、個々のイベント名の列挙ではなく
# `event.startswith("ctypes.")`という名前空間ごとのデフォルト拒否を
# 既に備えており、この欠陥の対象ではないことを実機で確認した
# (既存の未変更のコードのままで"ctypes.dlsym"が正しく遮断される
# ことを確認済み)。本天使は、maquina_gatekeeper.py側の修正
# ("ctypes.dlopen"・"ctypes.dlsym"をforbidden集合に追加)を継続的に
# 再検証し、同時にsefer側が(本修正を加えていない既存のコードの
# ままで)同じ攻撃に対して既に保護されていることも裏付けとして
# 検証する。
#
# [正直な注記: 本検査の限界] 本修正は「Sanctumに入った『後』に
# 新たにシンボルを解決・新たなハンドルを取得する」というパターンを
# 塞ぐものである。Sanctumに入る『前』に関数ポインタ自体を解決・
# 変数に保存しておけば、その後の呼び出し自体は新たなaudit eventを
# 一切発生させないため(実機で確認済み)、本修正・本天使のいずれも
# これには及ばない。これは本防御方式(audit hookベースの検査)
# 自体の限界であり、恒久対策にはOSレベルのサンドボックスが必要で
# ある。

sys.path.insert(0, str(ROOT))


def _run(script: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = "/tmp/rsa_stub:/usr/local/lib/python3.13/dist-packages:" + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=str(ROOT))


def _check_pythonapi_symbol_resolution_is_blocked() -> tuple:
    """封鎖されている間、ctypes.pythonapiからのシンボル解決自体が
    遮断され、ファイルが一切変更されないことを確認する。"""
    fd, victim = tempfile.mkstemp(prefix="chamuel_mg_victim_")
    os.close(fd)
    with open(victim, "wb") as f:
        f.write(b"original content, untouched so far............")
    try:
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
        if res.returncode != 0:
            return False, f"ctypes.pythonapi経由の攻撃が遮断されなかった: stdout={res.stdout} stderr={res.stderr}"
        if not os.path.exists(victim):
            return False, "遮断されたはずだが、ファイルが実際には削除されている"
        return True, "OK"
    finally:
        if os.path.exists(victim):
            os.remove(victim)


def _check_fresh_cdll_dlopen_is_blocked() -> tuple:
    """封鎖されている間、新たなctypes.CDLL(None)の取得自体
    (ctypes.dlopen)が遮断されることを確認する。"""
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
    if res.returncode != 0:
        return False, f"新規ctypes.CDLL(None)のdlopenが遮断されなかった: stdout={res.stdout} stderr={res.stderr}"
    return True, "OK"


def _check_pythonapi_still_works_when_unsealed() -> tuple:
    """[誤検知防止] 封鎖されていない間は、ctypes.pythonapi経由の
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
    if res.returncode != 0:
        return False, f"封鎖されていない間の正当な利用が誤って遮断された: stdout={res.stdout} stderr={res.stderr}"
    return True, "OK"


def _check_sefer_already_protected_without_modification() -> tuple:
    """[裏付け] 独立した別の防御層(sefer/__init__.py)は、本修正を
    一切加えていない既存のコードのままで、同じ攻撃を既存の名前空間
    デフォルト拒否によって正しく遮断することを確認する。"""
    fd, victim = tempfile.mkstemp(prefix="chamuel_sefer_victim_")
    os.close(fd)
    with open(victim, "wb") as f:
        f.write(b"original content, untouched so far............")
    try:
        script = f"""
import ctypes, os, sys
from sefer import Sanctum, LossOfAtaraxia

try:
    with Sanctum(allowed_dirs=["/tmp/chamuel_nonexistent_jail"]):
        c_unlink = ctypes.pythonapi.unlink
        c_unlink.argtypes = [ctypes.c_char_p]
        c_unlink({victim!r}.encode())
    sys.exit(1)
except LossOfAtaraxia:
    sys.exit(0)
"""
        res = _run(script)
        if res.returncode != 0:
            return False, f"sefer側が同じ攻撃を遮断しなかった(既存の防御が崩れている可能性): stdout={res.stdout} stderr={res.stderr}"
        if not os.path.exists(victim):
            return False, "遮断されたはずだが、ファイルが実際には削除されている"
        return True, "OK"
    finally:
        if os.path.exists(victim):
            os.remove(victim)


CHECKS = [
    ("maquina_gatekeeper.ultimate_audit_hook: ctypes.pythonapi経由の遮断", _check_pythonapi_symbol_resolution_is_blocked),
    ("maquina_gatekeeper.ultimate_audit_hook: 新規ctypes.CDLL(None) dlopenの遮断", _check_fresh_cdll_dlopen_is_blocked),
    ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止", _check_pythonapi_still_works_when_unsealed),
    ("sefer._michael_absolute_defense: 既存の名前空間デフォルト拒否による保護の裏付け", _check_sefer_already_protected_without_modification),
]


def run_battery():
    """ctypes.dlopen/dlsymによる既知の監査回避バイパス経路を、
    maquina_gatekeeper.pyに対して実際に与えて、正しく処理されるかを
    確認する。sefer側は本修正の対象外であることの裏付けも含む。
    戻り値: [(name, detail), ...] (失敗したものだけ)"""
    failures = []
    for name, check_fn in CHECKS:
        try:
            success, detail = check_fn()
        except BaseException as e:
            # [脆弱性修正 2026-10 §CO追記] sefer.LossOfAtaraxia等、
            # BaseExceptionを直接継承する例外は`except Exception`では
            # 捕捉されず、検査関数が想定外にそれを発生させた場合、
            # 本来「安全側に倒して失敗として報告する」はずの設計が
            # 機能せず、run_battery自体が未処理の例外で丸ごと落ちて
            # しまう(angels/hadraniel_socket_send_guard.pyの新設時に
            # 実機で発見)。KeyboardInterrupt/SystemExit等も含め
            # 広く捕捉するが、本関数の唯一の責務は「1件の検査関数の
            # 呼び出し結果を安全に報告する」ことであり、ここで拾った
            # 例外は再送出せずfailuresに記録するだけなので、プロセス
            # 全体の正常なシャットダウン経路を妨げない。
            failures.append((name, f"検査関数自体が例外を発生: {type(e).__name__}: {e}"))
            continue
        if not success:
            failures.append((name, detail))
    return failures


def main():
    failures = run_battery()
    if failures:
        detail = "; ".join(f"{n}({d})" for n, d in failures)
        report_fail(
            NAME,
            f"ctypes.dlopen/dlsymによる深層保護の監査回避バイパス防止に、"
            f"少なくとも1つの既知の問題が再発しています(§CEの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "ctypes.dlopen/dlsym経由の深層保護バイパス(ctypes.pythonapi経由の"
        "シンボル解決・新規CDLL(None)取得の両方)が正しく遮断され、"
        "非封鎖時の正当な利用は誤って遮断されず、独立したsefer側も"
        "既存の設計で同じ攻撃から保護されていることを確認しました。",
    )


if __name__ == "__main__":
    main()
