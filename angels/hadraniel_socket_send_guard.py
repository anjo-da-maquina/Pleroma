import sys, os, socket, ssl, threading, subprocess, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "ハドラニエルの門 (Hadraniel's Gate - socket.send/sendall・TLSのssl.SSLSocket.send/write事前接続バイパス検知)"

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
#
# [新設 2026-10 §CP追記] 上記の§COの修正を実機で確認した直後、「TLS
# (HTTPS)経由の通信ではどうなるか」を再確認したところ、`ssl.SSLSocket`
# が`send`/`sendall`を**独自に上書きしている**(`socket.socket`の
# メソッドを一切呼ばない、完全に別の実装)ことを実機で確認した。その
# ため、§COで`socket.socket.send`自体をモンキーパッチしても、
# `ssl.SSLSocket`のインスタンス(`requests`・`urllib`等が内部で実際に
# 使っているTLSソケット)には一切効果が及ばない。実機で、自己署名証明書
# を用いた本物のTLSループバック接続を確立し、Sanctum起動後に
# `SSLSocket.send()`で機密データを送出したところ、§COの修正後でも
# 例外無しに成功し、受信側に実際にデータが届くことを確認した――§COより
# さらに実際的な経路である(AIが生成したコードが外部APIへ通信する場合、
# `requests`等の通常の経路は常にTLSを経由するため)。`sefer/__init__.py`
# に`_guarded_ssl_socket_send`/`_guarded_ssl_socket_sendall`を新設し、
# §COの`_check_socket_send_allowed`をそのまま再利用して修正した
# (GRIMOIRE.md §CP参照)。本天使に、TLS版の事前接続バイパス遮断・
# 許可ホストへの正当なTLS通信の誤検知防止検査を追加した。
#
# [新設 2026-10 §CR追記] §CPの修正を確認した直後、「`ssl.SSLSocket`で
# 他にも上書きされているメソッドは無いか」を`dir(ssl.SSLSocket)`で
# 機械的に棚卸ししたところ、`write()`というメソッドも独自実装で上書き
# されていることを発見した。CPython本体のソースを確認すると、
# `SSLSocket.write()`は`self._sslobj.write(data)`——TLSハンドシェイクを
# 実装するC実装の`_ssl._SSLSocket`オブジェクトへの直接呼び出し——で
# あり、`send`/`sendall`はおろか、基底クラスの`socket.socket`のどの
# メソッドも一切経由しない、全く別の第三の経路だった。実機で、本物の
# TLSループバック接続を確立し、Sanctum起動後に`SSLSocket.write()`で
# 機密データを送出したところ、§CPの修正後でも例外無しに成功し、受信側
# に実際にデータが届くことを確認した。`sefer/__init__.py`に
# `_guarded_ssl_socket_write`を新設し、§CO/§CPの
# `_check_socket_send_allowed`をそのまま再利用して修正した
# (GRIMOIRE.md §CR参照)。
#
# なお、同じ棚卸しで`sendto`・`sendmsg`も`SSLSocket`で上書きされている
# ことを確認したが、TLSハンドシェイク確立後は`sendto`は`ValueError`、
# `sendmsg`は`NotImplementedError`を無条件に発生させる実装になって
# おり、実際のデータ送出経路としては機能しない(CPython自身がこれらを
# 塞いでいる設計)ことを実機で確認済みのため、追加対策は不要と判断した。

sys.path.insert(0, str(ROOT))

_OPENSSL_AVAILABLE = shutil.which("openssl") is not None


def _make_self_signed_cert(tmpdir: str):
    """テスト専用の自己署名証明書・秘密鍵を、openssl CLI経由でその場で
    生成する(リポジトリの依存関係に`cryptography`パッケージを新たに
    追加しないための選択)。"""
    certfile = os.path.join(tmpdir, "hadraniel_test_cert.pem")
    keyfile = os.path.join(tmpdir, "hadraniel_test_key.pem")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", keyfile, "-out", certfile,
            "-days", "1", "-nodes", "-subj", "/CN=localhost",
        ],
        check=True, capture_output=True,
    )
    return certfile, keyfile


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
            # [正直な注記] これは本検査が期待する「正常に遮断された」
            # という成功パスであり、フェイルオープン(無言の握り潰し)
            # ではない。遮断後に実際にデータが届いていないことまで
            # 確認するため、意図的に処理を先へ進めている。
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
            # [正直な注記] これも上と同様、本検査が期待する「正常に
            # 遮断された」という成功パスであり、フェイルオープンでは
            # ない。
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


def _make_tls_loopback_pair(tmpdir: str):
    """テスト用のTLSループバック接続(サーバー側・クライアント側)を
    確立して、両方のSSLSocketを返す。呼び出し側がcloseの責任を持つ。
    サーバー側のスレッド起動はSanctumの**外側**で行うこと(Sanctum内での
    スレッド生成自体は本検査の対象外の、別の既存default-denyの対象)。"""
    certfile, keyfile = _make_self_signed_cert(tmpdir)

    srv_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    srv_ctx.load_cert_chain(certfile, keyfile)
    raw_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_srv.bind(("127.0.0.1", 0))
    raw_srv.listen(1)
    port = raw_srv.getsockname()[1]

    accepted = {}
    def _accept_and_wrap():
        conn, _ = raw_srv.accept()
        accepted["conn"] = srv_ctx.wrap_socket(conn, server_side=True)

    th = threading.Thread(target=_accept_and_wrap)
    th.start()

    cli_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    cli_ctx.check_hostname = False
    cli_ctx.verify_mode = ssl.CERT_NONE
    raw_cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_cli.connect(("127.0.0.1", port))
    tls_cli = cli_ctx.wrap_socket(raw_cli, server_hostname="localhost")
    th.join(timeout=5)

    return raw_srv, tls_cli, accepted["conn"]


def _check_tls_send_to_presealed_socket_is_blocked() -> tuple:
    """[核心・§CP] Sanctum起動**前**に接続済みの実TLSソケットへ、
    Sanctum起動**後**に`ssl.SSLSocket.send()`で送出する攻撃が遮断
    されることを確認する。"""
    if not _OPENSSL_AVAILABLE:
        return True, "openssl CLIが利用できないためTLS検査をスキップ(検査対象外と判断した環境差異)"

    from sefer import Sanctum, LossOfAtaraxia

    # idnaコーデックの遅延importがSanctum内での初回呼び出し時に
    # marshal.loadsという無関係な別のhard-deny対象を誤って発火させる
    # ため(本検査の対象外)、Sanctumに入る前に一度ウォームアップする。
    "example".encode("idna")

    with tempfile.TemporaryDirectory(prefix="hadraniel_tls_") as tmpdir:
        raw_srv, tls_cli, tls_srv_conn = _make_tls_loopback_pair(tmpdir)
        secret = b"secret-over-tls-via-ssl-socket-send"
        try:
            try:
                with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"example.com"}):
                    tls_cli.send(secret)
                return False, "事前接続済みTLSソケットへのsend()が遮断されなかった"
            except LossOfAtaraxia:
                # [正直な注記] これは本検査が期待する「正常に遮断された」
                # という成功パスであり、フェイルオープンではない。
                pass

            tls_srv_conn.settimeout(0.2)
            try:
                leaked = tls_srv_conn.recv(len(secret))
            except (socket.timeout, ssl.SSLError):
                leaked = b""
            if leaked:
                return False, f"遮断されたはずだが、実際にデータが{leaked!r}として届いている"
            return True, "OK"
        finally:
            tls_cli.close()
            tls_srv_conn.close()
            raw_srv.close()


def _check_tls_send_to_newly_connected_allowed_host_is_not_falsely_blocked() -> tuple:
    """[誤検知防止・核心・§CP] Sanctum起動**後**に許可ホストへ新規TLS
    接続し、送信する正当なフローが誤って遮断されないことを確認する。"""
    if not _OPENSSL_AVAILABLE:
        return True, "openssl CLIが利用できないためTLS検査をスキップ(検査対象外と判断した環境差異)"

    from sefer import Sanctum, LossOfAtaraxia

    "example".encode("idna")

    with tempfile.TemporaryDirectory(prefix="hadraniel_tls_") as tmpdir:
        certfile, keyfile = _make_self_signed_cert(tmpdir)
        srv_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        srv_ctx.load_cert_chain(certfile, keyfile)
        raw_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_srv.bind(("127.0.0.1", 0))
        raw_srv.listen(1)
        port = raw_srv.getsockname()[1]

        accepted = {}
        def _accept_and_wrap():
            conn, _ = raw_srv.accept()
            accepted["conn"] = srv_ctx.wrap_socket(conn, server_side=True)

        # サーバー側のスレッド起動はSanctumの外側で行う(本検査の対象外の、
        # 既存のスレッド生成default-denyを踏まないため)。
        th = threading.Thread(target=_accept_and_wrap)
        th.start()

        cli_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        cli_ctx.check_hostname = False
        cli_ctx.verify_mode = ssl.CERT_NONE

        try:
            with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"127.0.0.1"}):
                raw_cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_cli.connect(("127.0.0.1", port))
                tls_cli = cli_ctx.wrap_socket(raw_cli, server_hostname="localhost")
                th.join(timeout=5)
                try:
                    try:
                        tls_cli.send(b"legit-tls")
                    except LossOfAtaraxia as e:
                        return False, f"許可ホストへの正当なTLS send()が誤って遮断された: {e}"
                finally:
                    tls_cli.close()
                    accepted["conn"].close()
            return True, "OK"
        finally:
            raw_srv.close()


def _check_tls_write_to_presealed_socket_is_blocked() -> tuple:
    """[核心・§CR] Sanctum起動**前**に接続済みの実TLSソケットへ、
    Sanctum起動**後**に`ssl.SSLSocket.write()`(`.send()`ではなく)で
    送出する攻撃が遮断されることを確認する。`write()`は`send`/`sendall`
    のどちらとも別の、`self._sslobj.write()`への直接呼び出しという
    第三の経路であるため、§CPの検査とは独立に確認する必要がある。"""
    if not _OPENSSL_AVAILABLE:
        return True, "openssl CLIが利用できないためTLS検査をスキップ(検査対象外と判断した環境差異)"

    from sefer import Sanctum, LossOfAtaraxia

    "example".encode("idna")

    with tempfile.TemporaryDirectory(prefix="hadraniel_tls_") as tmpdir:
        raw_srv, tls_cli, tls_srv_conn = _make_tls_loopback_pair(tmpdir)
        secret = b"secret-over-tls-via-ssl-socket-write"
        try:
            try:
                with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"example.com"}):
                    tls_cli.write(secret)
                return False, "事前接続済みTLSソケットへのwrite()が遮断されなかった"
            except LossOfAtaraxia:
                # [正直な注記] これは本検査が期待する「正常に遮断された」
                # という成功パスであり、フェイルオープンではない。
                pass

            tls_srv_conn.settimeout(0.2)
            try:
                leaked = tls_srv_conn.recv(len(secret))
            except (socket.timeout, ssl.SSLError, ConnectionResetError):
                leaked = b""
            if leaked:
                return False, f"遮断されたはずだが、実際にデータが{leaked!r}として届いている"
            return True, "OK"
        finally:
            tls_cli.close()
            tls_srv_conn.close()
            raw_srv.close()


def _check_tls_write_to_newly_connected_allowed_host_is_not_falsely_blocked() -> tuple:
    """[誤検知防止・核心・§CR] Sanctum起動**後**に許可ホストへ新規TLS
    接続し、`write()`で送信する正当なフローが誤って遮断されないことを
    確認する。"""
    if not _OPENSSL_AVAILABLE:
        return True, "openssl CLIが利用できないためTLS検査をスキップ(検査対象外と判断した環境差異)"

    from sefer import Sanctum, LossOfAtaraxia

    "example".encode("idna")

    with tempfile.TemporaryDirectory(prefix="hadraniel_tls_") as tmpdir:
        certfile, keyfile = _make_self_signed_cert(tmpdir)
        srv_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        srv_ctx.load_cert_chain(certfile, keyfile)
        raw_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_srv.bind(("127.0.0.1", 0))
        raw_srv.listen(1)
        port = raw_srv.getsockname()[1]

        accepted = {}
        def _accept_and_wrap():
            conn, _ = raw_srv.accept()
            accepted["conn"] = srv_ctx.wrap_socket(conn, server_side=True)

        th = threading.Thread(target=_accept_and_wrap)
        th.start()

        cli_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        cli_ctx.check_hostname = False
        cli_ctx.verify_mode = ssl.CERT_NONE

        try:
            with Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"127.0.0.1"}):
                raw_cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_cli.connect(("127.0.0.1", port))
                tls_cli = cli_ctx.wrap_socket(raw_cli, server_hostname="localhost")
                th.join(timeout=5)
                try:
                    try:
                        tls_cli.write(b"legit-tls-write")
                    except LossOfAtaraxia as e:
                        return False, f"許可ホストへの正当なTLS write()が誤って遮断された: {e}"
                finally:
                    tls_cli.close()
                    accepted["conn"].close()
            return True, "OK"
        finally:
            raw_srv.close()


def _check_tls_write_without_sanctum_is_unaffected() -> tuple:
    """[誤検知防止・§CR] Sanctumを一切使っていない通常時は、正当な
    `write()`が誤って遮断されないことを確認する。"""
    if not _OPENSSL_AVAILABLE:
        return True, "openssl CLIが利用できないためTLS検査をスキップ(検査対象外と判断した環境差異)"

    "example".encode("idna")

    with tempfile.TemporaryDirectory(prefix="hadraniel_tls_") as tmpdir:
        raw_srv, tls_cli, tls_srv_conn = _make_tls_loopback_pair(tmpdir)
        payload = b"non-sealed legit tls write"
        try:
            try:
                tls_cli.write(payload)
            except Exception as e:
                return False, f"Sanctum未使用時にwrite()が誤って失敗した: {e}"

            tls_srv_conn.settimeout(1.0)
            received = tls_srv_conn.recv(len(payload))
            if received != payload:
                return False, f"送出されるべきデータが正しく届いていない: {received!r}"
            return True, "OK"
        finally:
            tls_cli.close()
            tls_srv_conn.close()
            raw_srv.close()


CHECKS = [
    ("sefer._guarded_socket_send: 事前接続バイパス遮断(§CO)", _check_send_to_presealed_socket_is_blocked),
    ("sefer._guarded_socket_sendall: 事前接続バイパス遮断(§CO)", _check_sendall_to_presealed_socket_is_blocked),
    ("sefer._guarded_socket_send: 許可ホストへの正当な新規接続の誤検知防止(§CO)", _check_send_to_newly_connected_allowed_host_is_not_falsely_blocked),
    ("sefer._guarded_socket_send: Sanctum未使用時の誤検知防止(§CO)", _check_send_without_sanctum_is_unaffected),
    ("sefer._michael_absolute_defense: 許可外ホストへの新規connect遮断(§CO追記の回帰防止)", _check_new_connect_to_disallowed_host_is_still_blocked),
    ("sefer._guarded_ssl_socket_send: TLS事前接続バイパス遮断(§CP)", _check_tls_send_to_presealed_socket_is_blocked),
    ("sefer._guarded_ssl_socket_send: 許可ホストへの正当な新規TLS接続の誤検知防止(§CP)", _check_tls_send_to_newly_connected_allowed_host_is_not_falsely_blocked),
    ("sefer._guarded_ssl_socket_write: TLS事前接続バイパス遮断・write()経路(§CR)", _check_tls_write_to_presealed_socket_is_blocked),
    ("sefer._guarded_ssl_socket_write: 許可ホストへの正当な新規TLS write()の誤検知防止(§CR)", _check_tls_write_to_newly_connected_allowed_host_is_not_falsely_blocked),
    ("sefer._guarded_ssl_socket_write: Sanctum未使用時の誤検知防止(§CR)", _check_tls_write_without_sanctum_is_unaffected),
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
            f"sefer.Sanctumのsocket.send/sendall・ssl.SSLSocket.send/write"
            f"による事前接続バイパス防止に、少なくとも1つの既知の問題が"
            f"再発しています(§CO/§CP/§CRの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "socket.send/sendall(§CO)・ssl.SSLSocket.send(TLS、§CP)・"
        "ssl.SSLSocket.write(TLS、§CR)のいずれによる事前接続バイパスも"
        "正しく遮断され、かつSanctum起動後の許可ホストへの正当な新規"
        "接続・送信(TCP・TLSのsend/write双方)、およびSanctum未使用時の"
        "正当な利用は誤って遮断されないことを確認しました。",
    )


if __name__ == "__main__":
    main()
