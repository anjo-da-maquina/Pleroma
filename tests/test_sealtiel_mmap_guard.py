"""
tests/test_sealtiel_mmap_guard.py
====================================
[新設 2026-10 §CB] angels/sealtiel_mmap_guard.py の単体テスト。

実際に発見した具体例: `sefer/__init__.py`の`_michael_absolute_defense`は
"mmap.__new__"監査イベントを一度も検査していなかったため、Sanctumに
入る前に確保した書き込み用fdを`mmap.mmap(fd, length, access=...)`で
マップし、スライス代入で書き込むだけで、os.write系の既存対策を
完全に迂回して任意パスへ書き込めた。"mmap."を`monitored_namespaces`
に含め、fd経由で解決した実体パスのみに基づいて判定する(access値は
`prot=`/`flags=`方式では信頼できないため一切使わない)修正の、
継続的な再検証を本天使が担う。自己レッドチームの結果(`git stash`で
修正前の状態に戻すと正しくFAILし、復元すると正しくPASSすることを
確認済み)を回帰テストとして固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import sealtiel_mmap_guard as smg


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の実装が、全ての既知の状況を正しく処理する
    ことを確認する(§CBの修正の回帰防止)。"""
    failures = smg.run_battery()
    assert failures == [], f"検知に失敗した項目があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        smg.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_mmap_write_via_access_kwarg_is_blocked_directly():
    success, detail = smg._check_mmap_write_via_access_kwarg_is_blocked()
    assert success is True, detail


def test_check_mmap_write_via_prot_flags_kwargs_is_blocked_directly():
    """[核心] args[2](access)が信頼できない構築スタイルでも、
    fdベースの実体パス判定によって正しく遮断されることを確認する。"""
    success, detail = smg._check_mmap_write_via_prot_flags_kwargs_is_blocked()
    assert success is True, detail


def test_check_anonymous_mmap_is_not_falsely_blocked_directly():
    success, detail = smg._check_anonymous_mmap_is_not_falsely_blocked()
    assert success is True, detail


def test_check_mmap_write_inside_allowed_dirs_is_not_falsely_blocked_directly():
    success, detail = smg._check_mmap_write_inside_allowed_dirs_is_not_falsely_blocked()
    assert success is True, detail


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §CB修正前の、"mmap.__new__"を
    一切検査しない実装に戻した場合、本天使が正しく「遮断されなかった」
    として検知することを、実際に確認する。"""
    def _vulnerable_check():
        return False, "allowed_dirs外へのmmap書き込みが遮断されなかった(模擬)"

    patched_checks = [
        ("sefer._michael_absolute_defense: mmap access=方式の書き込み遮断", _vulnerable_check),
        ("sefer._michael_absolute_defense: 匿名mmapの誤検知防止", smg._check_anonymous_mmap_is_not_falsely_blocked),
    ]
    monkeypatch.setattr(smg, "CHECKS", patched_checks)

    failures = smg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "sefer._michael_absolute_defense: mmap access=方式の書き込み遮断"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(smg, "CHECKS", [("boom-checker", _boom)])
    failures = smg.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]
