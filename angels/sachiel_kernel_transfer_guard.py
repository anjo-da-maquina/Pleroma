import sys, os, socket, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "サキエルの水脈 (Sachiel's Waterway - os.sendfile/os.copy_file_rangeによるカーネル直接転送迂回検知)"

# [新設 2026-10 §CD] 実際に発見した具体例: §CBでmmapによるバイパスを
# 塞いだ直後、「os.write系4関数(os.write/os.pwrite/os.writev/
# os.pwritev)以外に、カーネル側でfdからfdへ直接データを転送する別の
# 経路はないか」を自問し、`sys.addaudithook`に生のコールバックを登録
# して実機で検証したところ、`os.sendfile(out_fd, in_fd, offset, count)`
# と`os.copy_file_range(src, dst, count)`の両方が、**CPythonのaudit
# eventを一切発生させない**ことを確認した。これはmmap.__new__のように
# 「監査すべきイベントが存在するのに検査していなかった」のとは異なり、
# そもそも監査可能なイベント自体が存在しない。両関数はいずれもカーネル
# の同名syscall相当を直接呼び、ユーザー空間のバッファ(os.write系が
# 引数として受け取るbytes)を一切経由しないため、既存のos.write系4関数
# のラップも一度も呼ばない。実機検証済み: allowed_dirs外のファイルに
# ついて、Sanctumに入る前に確保した書き込み用fdへ、別のfdから
# os.sendfileまたはos.copy_file_rangeで直接データを転送する攻撃が、
# 例外を一切発生させずに成功し、ファイル内容が実際に書き換わることを
# 確認した。
#
# [一般化の方針] これも本セッションで繰り返し発見している「意図は
# 同じ(fd事前オープンによる書き込み制限の迂回)だが、別のAPIを使う
# だけで素通りする」という構造の欠陥であり、§BW(import os.path)・
# §CA(socket.sendto)・§CB(mmap)と同種である。本天使は、実装詳細を
# 静的に解析するのではなく、実際にSanctumを起動し、既知の具体的な
# 迂回手口(sendfile/copy_file_rangeによるfd事前オープン書き込み)を
# 実行して、正しく遮断されることを継続的に検証する回帰連戦である。
#
# [正直な注記: 本検査の限界] 同じ調査の過程で、Sanctumに入る「前」に
# 確保したPythonファイルオブジェクト(`open(path, 'r+b')`等が返す
# `io.FileIO`/`io.BufferedWriter`)の`.write()`メソッドも、同様に
# 監査イベントを発生させず、本修正後もSanctumを完全に迂回して書き込め
# ることを実機で確認した。これはCPythonの`_io`拡張型のメソッドで、
# `io.FileIO.write = ...`のような通常の属性代入によるモンキーパッチが
# `TypeError: cannot set 'write' attribute of immutable type
# '_io.FileIO'`で拒否されることも実機で確認している(ctypesで型オブ
# ジェクトのメモリを直接書き換えるような極めて脆い手段を除く)。これは
# 「osモジュールの関数をPython層でラップする」という本防御方式自体の
# 限界であり、恒久対策にはOSレベルのサンドボックス(seccomp等)が必要
# である。本天使はこの既知の限界を再検証するものではなく、sendfile/
# copy_file_rangeという「修正可能だった」経路が実際に塞がれているかを
# 検証するものである。

sys.path.insert(0, str(ROOT))


def _victim_pair(victim_content: bytes, payload_content: bytes):
    """検査用の被害ファイルと攻撃元ファイルを作り、そのパスを返す。
    呼び出し側が削除責任を持つ。"""
    vfd, vpath = tempfile.mkstemp(prefix="sachiel_victim_")
    os.close(vfd)
    with open(vpath, "wb") as f:
        f.write(victim_content)
    pfd, ppath = tempfile.mkstemp(prefix="sachiel_payload_")
    os.close(pfd)
    with open(ppath, "wb") as f:
        f.write(payload_content)
    return vpath, ppath


def _check_sendfile_write_is_blocked() -> tuple:
    """Sanctumに入る前に確保した書き込み用fdへ、os.sendfile()で別の
    fdから直接データを転送する攻撃が遮断されることを確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    original = b"original content, untouched so far............"
    vpath, ppath = _victim_pair(original, b"PWNED_VIA_SENDFILE")
    try:
        dst_fd = os.open(vpath, os.O_WRONLY)
        src_fd = os.open(ppath, os.O_RDONLY)
        try:
            try:
                with Sanctum(allowed_dirs=["/tmp/sachiel_nonexistent_jail"]):
                    os.sendfile(dst_fd, src_fd, 0, 19)
                return False, "os.sendfileによる書き込みが遮断されなかった"
            except LossOfAtaraxia:
                # [正直な注記] これは本検査が期待する「正常に遮断された」
                # という成功パスであり、フェイルオープン(無言の握り潰し)
                # ではない。遮断後にファイル内容が実際に変更されていない
                # ことを確認するため、意図的に処理を先へ進めている。
                pass
        finally:
            os.close(dst_fd)
            os.close(src_fd)

        with open(vpath, "rb") as f:
            content = f.read()
        if content != original:
            return False, "遮断されたはずだが、ファイルの内容が実際には変更されている"
        return True, "OK"
    finally:
        os.remove(vpath)
        os.remove(ppath)


def _check_copy_file_range_write_is_blocked() -> tuple:
    """[核心] 同様の攻撃をos.copy_file_range()で行っても遮断されることを
    確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    original = b"original content 2, untouched........"
    vpath, ppath = _victim_pair(original, b"PWNED_VIA_COPY_FILE_RANGE")
    try:
        dst_fd = os.open(vpath, os.O_WRONLY)
        src_fd = os.open(ppath, os.O_RDONLY)
        try:
            try:
                with Sanctum(allowed_dirs=["/tmp/sachiel_nonexistent_jail"]):
                    os.copy_file_range(src_fd, dst_fd, 25)
                return False, "os.copy_file_rangeによる書き込みが遮断されなかった"
            except LossOfAtaraxia:
                # [正直な注記] これも上と同様、本検査が期待する「正常に
                # 遮断された」という成功パスであり、フェイルオープンでは
                # ない。
                pass
        finally:
            os.close(dst_fd)
            os.close(src_fd)

        with open(vpath, "rb") as f:
            content = f.read()
        if content != original:
            return False, "遮断されたはずだが、ファイルの内容が実際には変更されている"
        return True, "OK"
    finally:
        os.remove(vpath)
        os.remove(ppath)


def _check_sendfile_inside_allowed_dirs_is_not_falsely_blocked() -> tuple:
    """[誤検知防止] allowed_dirs内のファイルに対する正当なsendfileが
    引き続き許可されることを確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    with tempfile.TemporaryDirectory() as tmpdir:
        dst = os.path.join(tmpdir, "ok_dst.txt")
        src = os.path.join(tmpdir, "ok_src.txt")
        with open(src, "wb") as f:
            f.write(b"legit sendfile payload")
        open(dst, "wb").close()

        dst_fd = os.open(dst, os.O_WRONLY)
        src_fd = os.open(src, os.O_RDONLY)
        try:
            try:
                with Sanctum(allowed_dirs=[tmpdir]):
                    os.sendfile(dst_fd, src_fd, 0, 100)
            except LossOfAtaraxia as e:
                return False, f"allowed_dirs内への正当なsendfileが誤って遮断された: {e}"
        finally:
            os.close(dst_fd)
            os.close(src_fd)

        with open(dst, "rb") as f:
            content = f.read()
        if content != b"legit sendfile payload":
            return False, "書き込みが許可されるべきだったが、実際には反映されていない"
        return True, "OK"


def _check_copy_file_range_inside_allowed_dirs_is_not_falsely_blocked() -> tuple:
    """[誤検知防止] allowed_dirs内のファイルに対する正当な
    copy_file_rangeが引き続き許可されることを確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    with tempfile.TemporaryDirectory() as tmpdir:
        dst = os.path.join(tmpdir, "ok_dst.txt")
        src = os.path.join(tmpdir, "ok_src.txt")
        with open(src, "wb") as f:
            f.write(b"legit copy_file_range payload")
        open(dst, "wb").close()

        dst_fd = os.open(dst, os.O_WRONLY)
        src_fd = os.open(src, os.O_RDONLY)
        try:
            try:
                with Sanctum(allowed_dirs=[tmpdir]):
                    os.copy_file_range(src_fd, dst_fd, 100)
            except LossOfAtaraxia as e:
                return False, f"allowed_dirs内への正当なcopy_file_rangeが誤って遮断された: {e}"
        finally:
            os.close(dst_fd)
            os.close(src_fd)

        with open(dst, "rb") as f:
            content = f.read()
        if content != b"legit copy_file_range payload":
            return False, "書き込みが許可されるべきだったが、実際には反映されていない"
        return True, "OK"


# [新設 2026-10 §CN] §CDの修正(上記)は「fd事前オープンによる
# allowed_dirs外への**書き込み**」という観点のみを塞いだものだった。
# §CKの「続けて」作業の中で、同じos.sendfileについて別の観点――
# 送り先fdがファイルではなく**ソケット**である場合、ファイルの内容を
# そのままネットワーク経由で外部に送出できてしまう――を再検証したところ、
# `sefer/__init__.py`の`_resolve_fd_path`が、送り先fdが`"socket:"`で
# 始まるリンクに解決される場合、意図的に`None`を返して
# `_check_fd_write_allowed`のチェック自体をスキップしていたことが
# 判明した(ファイル書き込み制限の観点では「パスが存在しないので対象外」
# という正しい判断だったが、ネットワーク送出の観点では無検査のまま
# だったという副作用)。実機で、Sanctum起動**前**に接続済みの実TCP
# ソケットへ、Sanctum起動**後**にos.sendfileでファイル内容を送出する
# 攻撃が例外無しで成功し、受信側で実際にファイル内容を受信できることを
# 確認した(本物の情報持ち出し)。`_check_fd_not_socket_for_sendfile`を
# 新設してこの経路を明示的に拒否する修正の、継続的な再検証を本天使が
# 担う。
#
# [正直な注記: 本検査の限界] `os.copy_file_range`はLinuxカーネル側の
# 制約により、両端が通常ファイル(regular file)である場合のみ動作し、
# ソケットfdを渡すと`OSError(EINVAL)`になる(実機で確認済み)。そのため
# 本検査はos.sendfileのソケット経路のみを対象とし、copy_file_rangeの
# ソケット版は検査対象に含めていない(検査不要と判断した境界)。


def _check_sendfile_to_socket_is_blocked_end_to_end() -> tuple:
    """[核心・§CN] Sanctum起動**前**に接続済みの実ソケットへ、Sanctum
    起動**後**にos.sendfileでファイル内容を送出する攻撃が、実際に
    遮断されることを確認する(「事前オープンfdバイパス」の前提条件を
    満たした、完全な実攻撃チェーンでの検証)。"""
    from sefer import Sanctum, LossOfAtaraxia

    # Sanctum起動前に、実際のTCPループバック接続を確立する
    # (socket.connect自体はmichaelの深層保護で遮断されるため、
    #  ガードが有効になる前に接続を済ませておく必要がある)。
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.connect(("127.0.0.1", port))
    conn, _ = srv.accept()

    secret = b"secret-file-content-to-exfiltrate"
    vfd, vpath = tempfile.mkstemp(prefix="sachiel_secret_")
    os.write(vfd, secret)
    os.close(vfd)

    try:
        src_fd = os.open(vpath, os.O_RDONLY)
        try:
            try:
                with Sanctum(allowed_dirs=["/tmp/sachiel_nonexistent_jail"]):
                    os.sendfile(cli.fileno(), src_fd, 0, len(secret))
                return False, "os.sendfileによるソケットへの送出が遮断されなかった"
            except LossOfAtaraxia:
                # [正直な注記] これは本検査が期待する「正常に遮断された」
                # という成功パスであり、フェイルオープン(無言の握り潰し)
                # ではない。上の_check_sendfile_write_is_blocked等と同じ
                # 構造で、遮断後に実際にデータが届いていないことまで
                # 確認するため、意図的に処理を先へ進めている。
                pass
        finally:
            os.close(src_fd)

        # [正直な注記] 遮断後、実際にデータが届いていないことまで確認する
        # (例外が出ただけで、カーネル側では一部転送済みという可能性を
        # 排除するため)。ノンブロッキングで即座に確認する。
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
        os.remove(vpath)


def _check_sendfile_to_socket_without_sanctum_is_unaffected() -> tuple:
    """[誤検知防止・§CN] Sanctumを一切使っていない通常時(ガード非有効)
    は、ソケットへの正当なos.sendfileが誤って遮断されないことを確認
    する(本検査自体がsefer全体を誤作動させていないかの確認)。"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.connect(("127.0.0.1", port))
    conn, _ = srv.accept()

    payload = b"non-sealed legit sendfile"
    vfd, vpath = tempfile.mkstemp(prefix="sachiel_legit_")
    os.write(vfd, payload)
    os.close(vfd)

    try:
        src_fd = os.open(vpath, os.O_RDONLY)
        try:
            os.sendfile(cli.fileno(), src_fd, 0, len(payload))
        except Exception as e:
            return False, f"Sanctum未使用時にos.sendfileが誤って失敗した: {e}"
        finally:
            os.close(src_fd)

        conn.settimeout(1.0)
        received = conn.recv(len(payload))
        if received != payload:
            return False, f"送出されるべきデータが正しく届いていない: {received!r}"
        return True, "OK"
    finally:
        cli.close()
        conn.close()
        srv.close()
        os.remove(vpath)


CHECKS = [
    ("sefer._guarded_os_sendfile: fd事前オープン書き込み遮断", _check_sendfile_write_is_blocked),
    ("sefer._guarded_os_copy_file_range: fd事前オープン書き込み遮断", _check_copy_file_range_write_is_blocked),
    ("sefer._guarded_os_sendfile: allowed_dirs内の誤検知防止", _check_sendfile_inside_allowed_dirs_is_not_falsely_blocked),
    ("sefer._guarded_os_copy_file_range: allowed_dirs内の誤検知防止", _check_copy_file_range_inside_allowed_dirs_is_not_falsely_blocked),
    ("sefer._guarded_os_sendfile: ソケット宛送出遮断(§CN・事前接続バイパス込み)", _check_sendfile_to_socket_is_blocked_end_to_end),
    ("sefer._guarded_os_sendfile: Sanctum未使用時のソケット送出への誤検知防止(§CN)", _check_sendfile_to_socket_without_sanctum_is_unaffected),
]


def run_battery():
    """os.sendfile/os.copy_file_rangeによる既知のfd事前オープン迂回
    経路を実際に与えて、正しく処理されるかを確認する。
    戻り値: [(name, detail), ...] (失敗したものだけ)"""
    failures = []
    for name, check_fn in CHECKS:
        try:
            success, detail = check_fn()
        except Exception as e:
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
            f"Sanctumのos.sendfile/os.copy_file_rangeによるfd事前オープン"
            f"迂回防止(書き込み・ソケット送出の両方)に、少なくとも1つの"
            f"既知の問題が再発しています(§CD/§CNの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "os.sendfile/os.copy_file_rangeによるfd事前オープン書き込み"
        "バイパス(§CD)、およびos.sendfileによるソケット宛のネットワーク"
        "情報持ち出しバイパス(§CN)がいずれも正しく遮断され、かつ"
        "allowed_dirs内・Sanctum未使用時の正当な利用は誤って遮断されない"
        "ことを確認しました。",
    )


if __name__ == "__main__":
    main()
