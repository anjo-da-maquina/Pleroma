import sys, os, mmap, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "セアルティエルの眼差し (Sealtiel's Gaze - mmapによるfd事前オープン迂回検知)"

# [新設 2026-10 §CB] 実際に発見した具体例: `sefer/__init__.py`の
# `_michael_absolute_defense()`は、既に「fd事前オープンによる書き込み
# バイパス対策」(`_guarded_os_write`/`_guarded_os_pwrite`/
# `_guarded_os_writev`/`_guarded_os_pwritev`)を備えていたが、これは
# os.write系の4系統のみをラップするものであった。しかし
# `mmap.mmap(fd, length, access=mmap.ACCESS_WRITE)`で、Sanctumに
# 「入る前」に確保しておいた書き込み用fdをメモリへマップし、
# `mm[0:N] = b'...'`のようにスライス代入するだけで、os.write系APIを
# 一切呼ばずに任意パスへ書き込める。これはCPythonの正式な監査イベント
# "mmap.__new__"を発生させるにもかかわらず、本関数はこのイベントを
# 一度も検査していなかった(ハードデニー・ソケット・open/os.open・
# 削除系・リネーム系・デフォルト拒否のいずれにも一致せず、完全に
# 素通りしていた。実機検証済み: allowed_dirs外のファイルについて、
# Sanctumに入る前に確保したfdをmmapし、スライス代入で書き込む攻撃が、
# 例外を一切発生させずに成功することを確認した)。
#
# [一般化の方針] これは本セッションで繰り返し発見している「宣言された
# API/イベント名は特定の1つだけを対象にしているが、同じ危険な効果を
# 持つ別のAPI/イベント名が存在し、それを使うだけで素通りする」という
# 構造の欠陥であり、§BW(import os.path)・§CA(socket.sendto)と同種で
# ある。本天使は、`_michael_absolute_defense`の実装詳細を静的に解析
# するのではなく、実際にSanctumを起動し、既知の具体的な迂回手口
# (mmapによるfd事前オープン書き込み)を実行して、正しく遮断される
# ことを継続的に検証する回帰連戦である。
#
# [正直な注記: 本検査の限界] (1) "mmap.__new__"イベントのargs[2]
# (access)は、`access=`キーワード構築時は要求値を正しく報告するが、
# Unix系の`prot=`/`flags=`キーワード構築時は、実際にPROT_WRITEを
# 要求していても常に0を報告することを実機で確認した(匿名mmapと
# 判別不能)。そのため修正はaccess値を一切信用せず、fd経由で解決した
# 実体パスのみで判定する設計を採用しており、本天使はその両方の構築
# スタイル(access=方式とprot=/flags=方式)を実際に試して検証する。
# (2) 本天使が検証するのは「mmapによるfd事前オープン書き込み」という
# 既知の具体的な経路のみであり、将来Pythonが追加する別のメモリマップ
# 系APIには自動的には及ばない。(3) 本修正は意図的に「宣言上は読み取り
# 専用のmmapであっても、allowed_dirs外のファイルには一律遮断する」
# という安全側の設計を取っており、これはos.open/openの読み取り検査
# (restrict_reads時のみ遮断)より厳しい。本天使はこの設計判断自体を
# 疑うものではなく、その設計が実際に機能しているかのみを検証する。

sys.path.insert(0, str(ROOT))


def _victim_file(content: bytes):
    """検査用の一時ファイルを作り、そのパスを返す。呼び出し側が削除責任を持つ。"""
    fd, path = tempfile.mkstemp(prefix="sealtiel_mmap_victim_")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(content)
    return path


def _check_mmap_write_via_access_kwarg_is_blocked() -> tuple:
    """Sanctumに入る前に確保したfdを`access=mmap.ACCESS_WRITE`方式で
    mmapし、スライス代入による書き込みが遮断されることを確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    original = b"original content, untouched so far...."
    path = _victim_file(original)
    try:
        fd = os.open(path, os.O_RDWR)
        try:
            try:
                with Sanctum(allowed_dirs=["/tmp/sealtiel_nonexistent_jail"]):
                    mm = mmap.mmap(fd, 11, access=mmap.ACCESS_WRITE)
                    mm[0:11] = b"via mmap!!!"
                    mm.close()
                return False, "access=方式のmmap書き込みが遮断されなかった"
            except LossOfAtaraxia:
                # [正直な注記] これは本検査が期待する「正常に遮断された」
                # という成功パスであり、フェイルオープン(無言の握り潰し)
                # ではない。遮断が正しく発生した後、下のファイル内容
                # 検証(contentが変更されていないことの確認)に処理を進める
                # ために意図的にpassしている。
                pass
        finally:
            os.close(fd)

        with open(path, "rb") as f:
            content = f.read()
        if content != original:
            return False, "遮断されたはずだが、ファイルの内容が実際には変更されている"
        return True, "OK"
    finally:
        os.remove(path)


def _check_mmap_write_via_prot_flags_kwargs_is_blocked() -> tuple:
    """[核心] accessフィールドが信頼できない`prot=`/`flags=`方式でも、
    同じ攻撃が遮断されることを確認する。これがaccess値を信用しない
    設計(§CBの修正の核心)が実際に機能していることの直接の裏付け。"""
    from sefer import Sanctum, LossOfAtaraxia

    original = b"original content 2, untouched........"
    path = _victim_file(original)
    try:
        fd = os.open(path, os.O_RDWR)
        try:
            try:
                with Sanctum(allowed_dirs=["/tmp/sealtiel_nonexistent_jail"]):
                    mm = mmap.mmap(fd, 11, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)
                    mm[0:11] = b"via mmap!!!"
                    mm.close()
                return False, "prot=/flags=方式のmmap書き込みが遮断されなかった"
            except LossOfAtaraxia:
                # [正直な注記] これも上と同様、本検査が期待する「正常に
                # 遮断された」という成功パスであり、フェイルオープンでは
                # ない。遮断後にファイル内容が実際に変更されていないことを
                # 確認するため、意図的に処理を先へ進めている。
                pass
        finally:
            os.close(fd)

        with open(path, "rb") as f:
            content = f.read()
        if content != original:
            return False, "遮断されたはずだが、ファイルの内容が実際には変更されている"
        return True, "OK"
    finally:
        os.remove(path)


def _check_anonymous_mmap_is_not_falsely_blocked() -> tuple:
    """[誤検知防止] 匿名マッピング(fileno=-1)は実体ファイルを持たず
    持ち出しのリスクがないため、allowed_dirsが空でも誤って遮断されない
    ことを確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    try:
        with Sanctum(allowed_dirs=[]):
            mm = mmap.mmap(-1, 100)
            mm[0:5] = b"anon!"
            mm.close()
        return True, "OK"
    except LossOfAtaraxia as e:
        return False, f"匿名mmapが誤って遮断された: {e}"


def _check_mmap_write_inside_allowed_dirs_is_not_falsely_blocked() -> tuple:
    """[誤検知防止] allowed_dirs内のファイルに対する正当なmmap書き込み
    (fdをSanctumに入る前に確保した場合)が、引き続き許可されることを
    確認する。"""
    from sefer import Sanctum, LossOfAtaraxia

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "allowed.txt")
        with open(path, "wb") as f:
            f.write(b"hello world inside jail!!!!")

        fd = os.open(path, os.O_RDWR)
        try:
            try:
                with Sanctum(allowed_dirs=[tmpdir]):
                    mm = mmap.mmap(fd, 11, access=mmap.ACCESS_WRITE)
                    mm[0:11] = b"legit write"
                    mm.close()
            except LossOfAtaraxia as e:
                return False, f"allowed_dirs内への正当なmmap書き込みが誤って遮断された: {e}"
        finally:
            os.close(fd)

        with open(path, "rb") as f:
            content = f.read()
        if not content.startswith(b"legit write"):
            return False, "書き込みが許可されるべきだったが、実際には反映されていない"
        return True, "OK"


CHECKS = [
    ("sefer._michael_absolute_defense: mmap access=方式の書き込み遮断", _check_mmap_write_via_access_kwarg_is_blocked),
    ("sefer._michael_absolute_defense: mmap prot=/flags=方式の書き込み遮断", _check_mmap_write_via_prot_flags_kwargs_is_blocked),
    ("sefer._michael_absolute_defense: 匿名mmapの誤検知防止", _check_anonymous_mmap_is_not_falsely_blocked),
    ("sefer._michael_absolute_defense: allowed_dirs内mmap書き込みの誤検知防止", _check_mmap_write_inside_allowed_dirs_is_not_falsely_blocked),
]


def run_battery():
    """`_michael_absolute_defense`に対し、既知のmmapによるfd事前オープン
    迂回経路を実際に与えて、正しく処理されるかを確認する。
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
            f"Sanctumのmmapによるfd事前オープン迂回防止に、少なくとも1つの"
            f"既知の問題が再発しています(§CBの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "mmapによるfd事前オープン書き込みバイパス(access=方式・prot=/flags=方式"
        "の両方)が正しく遮断され、かつ匿名mmapおよびallowed_dirs内の正当な"
        "mmap書き込みは誤って遮断されないことを確認しました。",
    )


if __name__ == "__main__":
    main()
