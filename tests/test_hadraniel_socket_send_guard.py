"""
tests/test_hadraniel_socket_send_guard.py
====================================
[新設 2026-10 §CO] angels/hadraniel_socket_send_guard.py の単体テスト。

実際に発見した具体例: `socket.socket.send()`/`sendall()`は、CPythonの
audit eventを一切発生させない。`sefer/__init__.py`の既存の防御
(`_michael_absolute_defense`が"socket.connect"/"socket.sendto"/
"socket.sendmsg"をイベント名で監視)は、これらのイベント自体が発火
しないsend/sendallには一切及ばず、Sanctum起動前に接続済みのソケット
への、起動後のsend/sendallによるデータ送出が無条件に成功していた。
この経路を塞ぐ`_guarded_socket_send`/`_guarded_socket_sendall`の、
継続的な再検証を本天使が担う。

同じ調査の過程で、`allowed_hosts`を指定していても"socket.__new__"が
passthrough対象に含まれておらず、ソケット生成自体が常に無条件拒否
されていた(fail-closedの誤検知)別の欠陥も発見・修正した。

自己レッドチームの結果(修正前の状態に戻すと正しくFAILし、復元すると
正しくPASSすることを確認済み)を回帰テストとして固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import hadraniel_socket_send_guard as hsg


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の実装が、全ての既知の状況を正しく処理する
    ことを確認する(§COの修正の回帰防止)。"""
    failures = hsg.run_battery()
    assert failures == [], f"検知に失敗した項目があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        hsg.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_send_to_presealed_socket_is_blocked_directly():
    success, detail = hsg._check_send_to_presealed_socket_is_blocked()
    assert success is True, detail


def test_check_sendall_to_presealed_socket_is_blocked_directly():
    success, detail = hsg._check_sendall_to_presealed_socket_is_blocked()
    assert success is True, detail


def test_check_send_to_newly_connected_allowed_host_is_not_falsely_blocked_directly():
    success, detail = hsg._check_send_to_newly_connected_allowed_host_is_not_falsely_blocked()
    assert success is True, detail


def test_check_send_without_sanctum_is_unaffected_directly():
    success, detail = hsg._check_send_without_sanctum_is_unaffected()
    assert success is True, detail


def test_check_new_connect_to_disallowed_host_is_still_blocked_directly():
    success, detail = hsg._check_new_connect_to_disallowed_host_is_still_blocked()
    assert success is True, detail


def test_check_tls_send_to_presealed_socket_is_blocked_directly():
    """[新設 §CP] §CO(socket.send/sendall)の修正を実機で確認した直後、
    `ssl.SSLSocket`が`send`/`sendall`を独自に上書きしている(基底クラス
    `socket.socket`のメソッドを呼ばない)ため、§COの修正がTLS通信には
    一切及ばないことを発見した。本テストは、Sanctum起動前に接続済みの
    実TLSソケットへの、起動後のsend()による送出が遮断されることを、
    継続的に再検証する。"""
    success, detail = hsg._check_tls_send_to_presealed_socket_is_blocked()
    assert success is True, detail


def test_check_tls_send_to_newly_connected_allowed_host_is_not_falsely_blocked_directly():
    success, detail = hsg._check_tls_send_to_newly_connected_allowed_host_is_not_falsely_blocked()
    assert success is True, detail


def test_check_tls_write_to_presealed_socket_is_blocked_directly():
    """[新設 §CR] §CP(ssl.SSLSocket.send/sendall)の修正を実機で確認した
    直後、`dir(ssl.SSLSocket)`で同クラスの他のメソッドを機械的に棚卸し
    したところ、`write()`も独自実装で上書きされており、`self._sslobj.
    write()`への直接呼び出し――`send`/`sendall`のどちらとも別の、
    第三の経路――であることを発見した。Sanctum起動前に接続済みの実TLS
    ソケットへの、起動後のwrite()による送出が遮断されることを、本テスト
    が継続的に再検証する。"""
    success, detail = hsg._check_tls_write_to_presealed_socket_is_blocked()
    assert success is True, detail


def test_check_tls_write_to_newly_connected_allowed_host_is_not_falsely_blocked_directly():
    success, detail = hsg._check_tls_write_to_newly_connected_allowed_host_is_not_falsely_blocked()
    assert success is True, detail


def test_check_tls_write_without_sanctum_is_unaffected_directly():
    success, detail = hsg._check_tls_write_without_sanctum_is_unaffected()
    assert success is True, detail


def test_battery_detects_reintroduced_tls_write_bypass_regression(monkeypatch):
    """[核心・自己レッドチームの固定・§CR] `sefer/__init__.py`の
    `ssl.SSLSocket.write`が(将来の変更で)再び`_guarded_ssl_socket_write`
    に差し替えられなくなった場合、本天使が正しく「遮断されなかった」
    として検知することを、実際にgit stashでこの退行を再現して確認済み
    (修正前は本テストと同じ失敗を実機で確認し、修正後はPASSに戻ることを
    確認した)。"""
    def _vulnerable_check():
        return False, "事前接続済みTLSソケットへのwrite()が遮断されなかった(模擬)"

    patched_checks = [
        ("sefer._guarded_ssl_socket_write: TLS事前接続バイパス遮断・write()経路(§CR)", _vulnerable_check),
        ("sefer._guarded_ssl_socket_write: Sanctum未使用時の誤検知防止(§CR)", hsg._check_tls_write_without_sanctum_is_unaffected),
    ]
    monkeypatch.setattr(hsg, "CHECKS", patched_checks)

    failures = hsg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "sefer._guarded_ssl_socket_write: TLS事前接続バイパス遮断・write()経路(§CR)"


def test_battery_detects_reintroduced_send_bypass_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §CO修正前の、socket.send/sendallを
    一切ラップしない実装に戻した場合、本天使が正しく「遮断されなかった」
    として検知することを、実際にgit stashでこの退行を再現して確認済み
    (修正前は本テストと同じ失敗を実機で確認し、修正後はPASSに戻ることを
    確認した)。"""
    def _vulnerable_check():
        return False, "事前接続済みソケットへのsend()が遮断されなかった(模擬)"

    patched_checks = [
        ("sefer._guarded_socket_send: 事前接続バイパス遮断(§CO)", _vulnerable_check),
        ("sefer._guarded_socket_send: Sanctum未使用時の誤検知防止(§CO)", hsg._check_send_without_sanctum_is_unaffected),
    ]
    monkeypatch.setattr(hsg, "CHECKS", patched_checks)

    failures = hsg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "sefer._guarded_socket_send: 事前接続バイパス遮断(§CO)"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(hsg, "CHECKS", [("boom-checker", _boom)])
    failures = hsg.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]


def test_checker_base_exception_is_also_reported_as_a_failure(monkeypatch):
    """[新設・§CO追記の回帰防止] `sefer.LossOfAtaraxia`のように
    BaseExceptionを直接継承する例外を検査関数が想定外に発生させた場合も、
    run_battery自体が未処理の例外で丸ごと落ちるのではなく、安全側に
    倒して「失敗」として報告することを確認する(本天使の新設時に
    `except Exception`では捕捉できないことを実機で発見し、
    `except BaseException`へ修正した)。"""
    from sefer import LossOfAtaraxia

    def _boom_base_exception():
        raise LossOfAtaraxia("[Sefer] Tripwire: simulated")

    monkeypatch.setattr(hsg, "CHECKS", [("base-exception-boom-checker", _boom_base_exception)])
    failures = hsg.run_battery()
    assert len(failures) == 1
    assert "LossOfAtaraxia" in failures[0][1]
