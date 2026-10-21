"""
tests/test_jegudiel_exfiltration_guard.py
============================================
[新設 2026-10 §CA] angels/jegudiel_exfiltration_guard.py の単体テスト。

実際に発見した具体例: `maquina_gatekeeper.py`の`ultimate_audit_hook`
("深層保護")は、ネットワーク通信の遮断を"socket.connect"のみで行って
いたが、UDPの`socket.sendto()`は事前の`connect()`を一切必要とせずに
データを送信できるため、封鎖中でもこの経路からの情報持ち出しが例外無く
素通りしていた。forbidden集合に"socket.sendto"を追加した修正の、
継続的な再検証を本天使が担う。自己レッドチームの結果(`git stash`で
修正前の状態に戻すと正しくFAILし、復元すると正しくPASSすることを
確認済み)を回帰テストとして固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import jegudiel_exfiltration_guard as jeg


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の実装が、両方の既知の状況を正しく処理する
    ことを確認する(§CAの修正の回帰防止)。"""
    failures = jeg.run_battery()
    assert failures == [], f"検知に失敗した項目があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        jeg.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_udp_sendto_is_blocked_while_sealed_directly():
    success, detail = jeg._check_udp_sendto_is_blocked_while_sealed()
    assert success is True, detail


def test_check_udp_sendto_is_allowed_when_unsealed_directly():
    success, detail = jeg._check_udp_sendto_is_allowed_when_unsealed()
    assert success is True, detail


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §CA修正前の、"socket.connect"のみを
    遮断する素朴な実装に戻した場合、本天使が正しく「遮断されなかった」
    として検知することを、実際に確認する。"""
    def _vulnerable_check():
        return False, "封鎖中にsocket.sendto()によるデータ送信が遮断されなかった(模擬)"

    patched_checks = [
        ("maquina_gatekeeper.ultimate_audit_hook: UDP sendto遮断", _vulnerable_check),
        ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止", jeg._check_udp_sendto_is_allowed_when_unsealed),
    ]
    monkeypatch.setattr(jeg, "CHECKS", patched_checks)

    failures = jeg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "maquina_gatekeeper.ultimate_audit_hook: UDP sendto遮断"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(jeg, "CHECKS", [("boom-checker", _boom)])
    failures = jeg.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]
