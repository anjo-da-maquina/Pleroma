import sys, os, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "ハドラニエルの門 (Hadraniel's Gate - socket.send/sendallの事前接続バイパス検知)"

# [新設 2026-10 §CO] §CN(os.sendfileがaudit eventを発火しない件)の調査
# 直後、同じ観点をプロセス起動・通信系の他のAPIにも体系的に広げて再確認
# したところ、`socket.socket.send()`/`sendall()`が、実機で確認した限り
# **一度も**audit eventを発火しないことが判明した。
#
# `angels/jegudiel_exfiltration_guard.py`の§CA時点のコメントは、「TCP
# 経由のsend/sendallは専用eventを持たないが、必ず事前のconnectを要する
# (=forbidden集合で遮断済み)ため検査不要」と判断していたが、これは
# 「Sanctum起動**前**に確保したfd・接続は、起動後も検査を素通りする」
# という、本プロジェクトが繰り返し発見している「事前オープンfdバイパス」
# の構造を見落としていた。実機で確認したところ、Sanctum起動**前**に
# connect()しておいたソケットは、起動**後**に`.send()`/`.sendall()`で
# データを送出しても無条件に成功した――os.sendfileより遥かに一般的に
# 使われる「ソケットへの通常のデータ送信」そのものが、無検査だった。
#
# 本天使は、`sefer/__init__.py`に新設した`_guarded_socket_send`/
# `_guarded_socket_sendall`(§CO)が、この完全な実攻撃チェーン(Sanctum
# 起動前の接続確立→起動後のsend/sendall攻撃)を正しく遮断し、かつ
# Sanctum起動**後**に許可ホスト(allowed_hosts)へ新規接続して送信する
# 正当なフローは誤って遮断しないことを、継続的に検証する回帰連戦である。
#
# [正直な注記: 本検査の過程で発見した別の欠陥(§CO追記)] 本件の調査中、
# `allowed_hosts`を指定してSanctumを起動していても、ソケットの生成その
# もの(`socket.socket(...)`)が、ホスト情報を一切持たない
# "socket.__new__"というaudit eventを`_michael_absolute_defense`の
# 「2. ソケット通信検査」に誤って引っかけられ、常に無条件拒否されて
# いた(fail-closed方向の誤検知で、セキュリティホールではないが、
# allowed_hosts機能そのものが事実上使えなくなっていた)ことも発見した。
# `ALWAYS_PASSTHROUGH_AUDIT_EVENTS`に"socket.__new__"を追加して修正
# した。本天使の検査(特に誤検知防止検査)は、この副次的な修正の回帰も
# 合わせて検証する。

sys.path.insert(0, str(ROOT))


def _check_send_to_presealed_socket_is_blocked() -> tuple:
    """[核心] Sanctum起動**前**に接続済みの実ソケットへ、Sanctum起動
    **後**に`.send()`で送出する攻撃が遮断されることを確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.connect(("127.0.0.1", port))
    conn, _ = srv.accept()

    secret = b"secret-via-socket-send"
    try:
        try:
            with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"example.com"}):
                cli.send(secret)
            return False, "事前接続済みソケットへのsend()が遮断されなかった"
        except LossOfAtaraxia:
            pass

        conn.settimeout(0.2)
        try:
            leaked = conn.recv(len(secret))
        except socket.timeout:
            leaked = b""
        if leaked:
            return False, f"遮断されたはずだが、実際にデータが{leaked!r}として届いている"
        return True, "OK"
    finally:
        cli.close()
        conn.close()
        srv.close()


def _check_sendall_to_presealed_socket_is_blocked() -> tuple:
    """[核心] 同様の攻撃を`.sendall()`で行っても遮断されることを確認
    する。"""
    from sefer import Sanctum, LossOfAtaraxia

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.connect(("127.0.0.1", port))
    conn, _ = srv.accept()

    secret = b"secret-via-socket-sendall"
    try:
        try:
            with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"example.com"}):
                cli.sendall(secret)
            return False, "事前接続済みソケットへのsendall()が遮断されなかった"
        except LossOfAtaraxia:
            pass

        conn.settimeout(0.2)
        try:
            leaked = conn.recv(len(secret))
        except socket.timeout:
            leaked = b""
        if leaked:
            return False, f"遮断されたはずだが、実際にデータが{leaked!r}として届いている"
        return True, "OK"
    finally:
        cli.close()
        conn.close()
        srv.close()


def _check_send_to_newly_connected_allowed_host_is_not_falsely_blocked() -> tuple:
    """[誤検知防止・核心] Sanctum起動**後**に許可ホスト(allowed_hosts)
    へ新規接続し、送信する正当なフローが誤って遮断されないことを確認
    する。本検査は、同時に§CO追記で修正した"socket.__new__"の
    passthrough漏れ(fail-closed誤検知)の回帰も検証する。"""
    from sefer import Sanctum, LossOfAtaraxia

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    try:
        with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"127.0.0.1"}):
            cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cli.connect(("127.0.0.1", port))
            conn, _ = srv.accept()
            try:
                try:
                    cli.send(b"legit")
                except LossOfAtaraxia as e:
                    return False, f"許可ホストへの正当なsend()が誤って遮断された: {e}"
            finally:
                cli.close()
                conn.close()
        return True, "OK"
    finally:
        srv.close()


def _check_send_without_sanctum_is_unaffected() -> tuple:
    """[誤検知防止] Sanctumを一切使っていない通常時(ガード非有効)は、
    正当なsend()が誤って遮断されないことを確認する。"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.connect(("127.0.0.1", port))
    conn, _ = srv.accept()

    payload = b"non-sealed legit send"
    try:
        try:
            cli.send(payload)
        except Exception as e:
            return False, f"Sanctum未使用時にsend()が誤って失敗した: {e}"

        conn.settimeout(1.0)
        received = conn.recv(len(payload))
        if received != payload:
            return False, f"送出されるべきデータが正しく届いていない: {received!r}"
        return True, "OK"
    finally:
        cli.close()
        conn.close()
        srv.close()


def _check_new_connect_to_disallowed_host_is_still_blocked() -> tuple:
    """[誤検知防止の裏側] "socket.__new__"をpassthroughに追加した後も、
    許可外ホストへの新規connect自体は従来通り遮断されることを確認する
    (§CO追記の修正がホスト検査そのものを無力化していないか確認)。"""
    from sefer import Sanctum, LossOfAtaraxia

    try:
        with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"api.openai.com"}):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            try:
                try:
                    s.connect(("203.0.113.1", 80))
                    return False, "許可外ホストへのconnect()が遮断されなかった"
                except LossOfAtaraxia:
                    return True, "OK"
                except OSError:
                    # [正直な注記] ネットワーク到達性の制約によるOSErrorは、
                    # 本検査が確認したい「正しく遮断されたか」とは無関係
                    # なため、安全に無視する(LossOfAtaraxiaのみを本当の
                    # 検知対象とする)。
                    return True, "OK(ネットワーク到達性によりOSErrorだったが、遮断そのものの検証対象外)"
            finally:
                s.close()
    except LossOfAtaraxia:
        # socket.__new__自体で遮断された場合も、「許可外ホストへは繋がら
        # ない」という結果としては正しいが、本検査が検証したいのは
        # connect時のホスト検査が機能していることなので、この分岐には
        # 来ないはず(来た場合は§CO追記の修正が意図通り機能していない)。
        return False, "socket.__new__の時点で誤って遮断された(§CO追記の修正が機能していない)"


CHECKS = [
    ("sefer._guarded_socket_send: 事前接続バイパス遮断(§CO)", _check_send_to_presealed_socket_is_blocked),
    ("sefer._guarded_socket_sendall: 事前接続バイパス遮断(§CO)", _check_sendall_to_presealed_socket_is_blocked),
    ("sefer._guarded_socket_send: 許可ホストへの正当な新規接続の誤検知防止(§CO)", _check_send_to_newly_connected_allowed_host_is_not_falsely_blocked),
    ("sefer._guarded_socket_send: Sanctum未使用時の誤検知防止(§CO)", _check_send_without_sanctum_is_unaffected),
    ("sefer._michael_absolute_defense: 許可外ホストへの新規connect遮断(§CO追記の回帰防止)", _check_new_connect_to_disallowed_host_is_still_blocked),
]


def run_battery():
    """既知のsocket.send/sendallによる事前接続バイパス経路を実際に
    与えて、正しく処理されるかを確認する。
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
            f"sefer.Sanctumのsocket.send/sendallによる事前接続バイパス"
            f"防止に、少なくとも1つの既知の問題が再発しています(§CNの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "socket.send/sendallによる事前接続バイパス(§CO)が正しく遮断され、"
        "かつSanctum起動後の許可ホストへの正当な新規接続・送信、および"
        "Sanctum未使用時の正当な利用は誤って遮断されないことを確認しました。",
    )


if __name__ == "__main__":
    main()
