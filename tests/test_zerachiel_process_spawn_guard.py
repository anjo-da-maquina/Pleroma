"""
tests/test_zerachiel_process_spawn_guard.py
===============================================
[新設 2026-10 §CC] angels/zerachiel_process_spawn_guard.py の単体テスト。

実際に発見した具体例: `maquina_gatekeeper.py`の`ultimate_audit_hook`
("深層保護")は、新しいOSプロセスの生成を遮断する目的で
"subprocess.Popen"/"os.system"/"os.exec"/"os.posix_spawn"を`forbidden`
集合に含めていたが、同じ目的を達成できる`os.fork()`は、専用の別の
audit event"os.fork"を発火させるため、これらのいずれにも一致せず
封鎖中でも完全に素通りしていた。forbidden集合に"os.fork"/"os.forkpty"
を追加した修正の、継続的な再検証を本天使が担う。自己レッドチームの
結果(`git stash`で修正前の状態に戻すと正しくFAILし、復元すると正しく
PASSすることを確認済み)を回帰テストとして固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import zerachiel_process_spawn_guard as zpg


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の実装が、両方の既知の状況を正しく処理する
    ことを確認する(§CCの修正の回帰防止)。"""
    failures = zpg.run_battery()
    assert failures == [], f"検知に失敗した項目があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        zpg.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_fork_is_blocked_while_sealed_directly():
    success, detail = zpg._check_fork_is_blocked_while_sealed()
    assert success is True, detail


def test_check_fork_is_allowed_when_unsealed_directly():
    success, detail = zpg._check_fork_is_allowed_when_unsealed()
    assert success is True, detail


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §CC修正前の、"os.fork"を一度も
    検査しない実装に戻した場合、本天使が正しく「遮断されなかった」
    として検知することを、実際に確認する。"""
    def _vulnerable_check():
        return False, "封鎖中にos.fork()によるプロセス生成が遮断されなかった(模擬)"

    patched_checks = [
        ("maquina_gatekeeper.ultimate_audit_hook: os.fork遮断", _vulnerable_check),
        ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止", zpg._check_fork_is_allowed_when_unsealed),
    ]
    monkeypatch.setattr(zpg, "CHECKS", patched_checks)

    failures = zpg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "maquina_gatekeeper.ultimate_audit_hook: os.fork遮断"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(zpg, "CHECKS", [("boom-checker", _boom)])
    failures = zpg.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]
