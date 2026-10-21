"""
tests/test_sandalphon_rejection_memory_guard.py
=================================================
[新設 2026-10 §BZ] angels/sandalphon_rejection_memory_guard.py の単体テスト。

実際に発見した具体例: `tartarus/armageddon_core.py`の`apply_new_seal()`は、
過去に人間が明示的に"REJECTED"(拒否)した提案までも「既に提案済み」と
扱ってしまい、Armageddon Engineが同じ事件名で全く新しい侵入を実証しても
二度と再提案できなくなっていた。重複チェックを「現在も承認待ちの提案」
のみに限定する修正の、継続的な再検証を本天使が担う。自己レッドチームの
結果(`git stash`で修正前の状態に戻すと正しくFAILし、復元すると正しく
PASSすることを確認済み)を回帰テストとして固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import sandalphon_rejection_memory_guard as srmg


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の実装が、両方の既知の状況を正しく処理する
    ことを確認する(§BZの修正の回帰防止)。"""
    failures = srmg.run_battery()
    assert failures == [], f"検知に失敗した項目があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        srmg.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_reproposal_after_rejection_is_accepted_directly():
    success, detail = srmg._check_reproposal_after_rejection_is_accepted()
    assert success is True, detail


def test_check_still_open_duplicate_is_still_rejected_directly():
    success, detail = srmg._check_still_open_duplicate_is_still_rejected()
    assert success is True, detail


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §BZ修正前の、statusを問わず重複と
    みなす素朴な実装に戻した場合、本天使が正しく「再提案が受理されな
    かった」として検知することを、実際に確認する。"""
    def _vulnerable_check():
        return False, "過去にREJECTEDとなった事件名への新たな再提案が、永久に受理されなかった(模擬)"

    patched_checks = [
        ("apply_new_seal: REJECTED後の再提案が受理される", _vulnerable_check),
        ("apply_new_seal: 開いている重複提案は依然として防がれる", srmg._check_still_open_duplicate_is_still_rejected),
    ]
    monkeypatch.setattr(srmg, "CHECKS", patched_checks)

    failures = srmg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "apply_new_seal: REJECTED後の再提案が受理される"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(srmg, "CHECKS", [("boom-checker", _boom)])
    failures = srmg.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]
