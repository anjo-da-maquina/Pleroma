import sys, os, tempfile
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


CHECKS = [
    ("sefer._guarded_os_sendfile: fd事前オープン書き込み遮断", _check_sendfile_write_is_blocked),
    ("sefer._guarded_os_copy_file_range: fd事前オープン書き込み遮断", _check_copy_file_range_write_is_blocked),
    ("sefer._guarded_os_sendfile: allowed_dirs内の誤検知防止", _check_sendfile_inside_allowed_dirs_is_not_falsely_blocked),
    ("sefer._guarded_os_copy_file_range: allowed_dirs内の誤検知防止", _check_copy_file_range_inside_allowed_dirs_is_not_falsely_blocked),
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
            f"迂回防止に、少なくとも1つの既知の問題が再発しています"
            f"(§CDの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "os.sendfile/os.copy_file_rangeによるfd事前オープン書き込み"
        "バイパスが正しく遮断され、かつallowed_dirs内の正当な利用は"
        "誤って遮断されないことを確認しました。",
    )


if __name__ == "__main__":
    main()
