"""
tests/test_chamuel_dlsym_guard.py
====================================
[新設 2026-10 §CE] angels/chamuel_dlsym_guard.py の単体テスト。

実際に発見した具体例: `maquina_gatekeeper.py`の`forbidden`集合は
封鎖中に新たに`ctypes`をimportすることだけを遮断していたが、
`ctypes`が封鎖の『前』に一度でもimportされていれば、攻撃者は封鎖後
に改めてimportし直す必要が一切ない。既にimport済みの`ctypes`から
`ctypes.pythonapi`や新規`ctypes.CDLL(None)`でシンボルを解決する操作
(それぞれ"ctypes.dlsym"・"ctypes.dlopen"というaudit eventを発生
させる)のいずれも、この`forbidden`集合とは一度も一致せず、封鎖中
でも完全に素通りしていた。独立した別の防御層(`sefer/__init__.py`)
は名前空間ごとのデフォルト拒否を既に備えており対象外であることも
併せて検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import chamuel_dlsym_guard as cdg


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の実装が、全ての既知の状況を正しく処理する
    ことを確認する(§CEの修正の回帰防止)。"""
    failures = cdg.run_battery()
    assert failures == [], f"検知に失敗した項目があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        cdg.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_pythonapi_symbol_resolution_is_blocked_directly():
    success, detail = cdg._check_pythonapi_symbol_resolution_is_blocked()
    assert success is True, detail


def test_check_fresh_cdll_dlopen_is_blocked_directly():
    success, detail = cdg._check_fresh_cdll_dlopen_is_blocked()
    assert success is True, detail


def test_check_pythonapi_still_works_when_unsealed_directly():
    success, detail = cdg._check_pythonapi_still_works_when_unsealed()
    assert success is True, detail


def test_check_sefer_already_protected_without_modification_directly():
    success, detail = cdg._check_sefer_already_protected_without_modification()
    assert success is True, detail


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §CE修正前の、ctypes.dlopen/dlsym
    を一切検査しない実装に戻した場合、本天使が正しく「遮断されなかっ
    た」として検知することを、実際に確認する。"""
    def _vulnerable_check():
        return False, "ctypes.pythonapi経由の攻撃が遮断されなかった(模擬)"

    patched_checks = [
        ("maquina_gatekeeper.ultimate_audit_hook: ctypes.pythonapi経由の遮断", _vulnerable_check),
        ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止", cdg._check_pythonapi_still_works_when_unsealed),
    ]
    monkeypatch.setattr(cdg, "CHECKS", patched_checks)

    failures = cdg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "maquina_gatekeeper.ultimate_audit_hook: ctypes.pythonapi経由の遮断"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(cdg, "CHECKS", [("boom-checker", _boom)])
    failures = cdg.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]
