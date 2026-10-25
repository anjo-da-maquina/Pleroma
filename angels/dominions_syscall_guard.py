import sys, os, re, json, ctypes, socket, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, report_inconclusive, ROOT

NAME = "ドミニオンの統治 (Dominions' Dominion - seccompによるシステムコール次元のカーネルレベル支配の検知)"

# [新設 2026-10 §CG] §CFで導入したLinuxケーパビリティの剥奪は「root相当
# の特権の有無」を制御するものだったが、§CD・§CEで繰り返し発見した
# 「Sanctumに入る前に確保済みのfd・関数ポインタを使った迂回」は、
# いずれも特権を一切必要としない、無権限プロセスのままでも到達できる
# 操作だった(既に開いているfdへの書き込み自体はCAP_DAC_OVERRIDE等を
# 必要としない)。§CFの残存する限界(1)で正直に記した通りである。
#
# 本件は、ユーザーより「OSレベルのサンドボックスを準備するってどう
# いうこと?」との質問への回答で説明した、より直接的な対策――本来必要
# なシステムコールのみを許可するseccompプロファイルによる、カーネル
# レベルでのsyscall単位の制御――に実際に着手したものである。
#
# [設計方針の正直な開示] §CFと同じ制約(この調査環境のネットワーク
# 許可一覧がコンテナレジストリへの到達を遮断しており、`docker build`で
# `python:3.11-alpine`イメージ自体が取得できない)により、実際の
# コンテナ内で全syscallを網羅的にstraceして真に必要な許可リストを
# 実証的に洗い出すことができない。そこで本プロファイル
# (`src/sandalphon/seccomp-profile.json`)は、defaultAction を
# SCMP_ACT_ALLOW とするdenylist方式を採用した――個々の危険な
# システムコール(プロセス生成・ptrace・mount・カーネルモジュール・
# 特権関連・生ソケット・時刻変更・NUMA/keyring)を明示的にERRNO拒否
# するが、それ以外は既定で許可する。これは「正しく構成できたことを
# 実機で確認できないまま、本番のサンドボックスの基本機能を静かに
# 壊すかもしれない」という、より危険な失敗モードを避けるための、
# 現時点で誠実に検証可能な選択である。将来、実際にコンテナイメージへ
# 到達できる環境(GitHub Actions等)でstraceによる網羅的な洗い出しを
# 行い、真の default-deny 方式(allowlist)へ移行することを、正直な
# 未着手の課題として残す。
#
# 本天使は3段階の検証を行う: (A) プロファイルJSON自体の静的な健全性
# (denylistの中核項目が後退していないか)、(B) `run_in_sandalphon()`
# が実際にこのプロファイルを`docker run`へ渡しているかの静的確認、
# (C) Dockerを一切使わず、libseccomp(C ABI)への直接ctypes呼び出しで
# 実際にこのプロファイルと同じdenylistをこの実機のカーネルへロードし、
# 列挙された各システムコールが本当にEPERMで拒否され、かつ良性の操作
# (getpid・ファイルの読み書き)は引き続き成功することを、対照実験
# (フィルタ未ロード時は同じ操作が成功すること)付きで実機確認する。
# (C)はDockerデーモン・コンテナレジストリのいずれにも依存しないため、
# 本調査環境でも常に実行可能であり、§CFのように常時INCONCLUSIVEに
# 頼る必要がない。(D)として、Dockerが実際に使える場合は追加でコンテナ
# 内の実地検証も試みるが、この環境ではこれまで同様イメージ取得に
# 失敗するため、ここは§CFと同じくINCONCLUSIVEとして正直に報告する。

_PROFILE_PATH = ROOT / "src" / "sandalphon" / "seccomp-profile.json"

# [正直な注記] この一覧は「後退検知のための最小限の核」であり、
# プロファイルJSON全体の完全な複製ではない。プロファイル側で項目が
# 増えることは問題ないが、ここに列挙した核心項目が消えていれば、
# §CGで塞いだ具体的な迂回経路のいずれかが再び開いてしまったことを
# 意味する。
# [§CI訂正] execve・execveatは意図的にこの一覧から除外している。
# §CGでは当初これらも核心的な拒否対象に含めていたが、実際にGitHub
# Actions上でDocker経由の動的検証(§CGまでこの調査環境では常時
# INCONCLUSIVEだった(D)の段)が初めて実行された際、
# `exec /usr/local/bin/python: operation not permitted`でコンテナの
# 起動自体が失敗するという、自分自身が引き起こした回帰を発見した。
# Docker/runcは本プロファイルのseccompフィルタをコンテナのPID1へ
# ロードした上で、そのPID1自身にENTRYPOINT(`python`)をexecveさせて
# 起動するため、execveを拒否対象に含めると隔離結界そのものが二度と
# 起動できなくなる。fork/vfork/clone/clone3を拒否し続ける限り、
# Linuxでは新規プロセスの生成自体(posix_spawnやos.exec系も内部で
# これらのいずれかを経由する)がそもそも不可能であり、これが本来
# 塞ぎたかった迂回経路であるため、execveの許可自体は実質的な後退
# ではない。詳細はGRIMOIRE.md §CI参照。
_REQUIRED_CORE_DENYLIST = {
    "fork", "vfork", "clone", "clone3",
    "ptrace", "mount", "umount2", "chroot",
    "socket", "connect", "bind",
    "setuid", "setgid", "capset",
    "init_module", "reboot",
}

# [§CI] execve/execveatは逆に「denylistに含まれていてはならない」
# ことを静的に検査する――§CGの誤りを再び踏まないための回帰防止。
_FORBIDDEN_FROM_DENYLIST = {"execve", "execveat"}


def _check_profile_json_is_well_formed() -> tuple:
    """seccomp-profile.json自体が、denylist方式として正しい構造を保ち、
    §CGで塞いだ核心的なシステムコール群を引き続き拒否対象に含んでいる
    ことを静的に確認する。"""
    if not _PROFILE_PATH.exists():
        return False, f"プロファイルファイルが見つかりません: {_PROFILE_PATH}"
    try:
        profile = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, f"プロファイルJSONの構文が不正です: {e}"

    if profile.get("defaultAction") != "SCMP_ACT_ALLOW":
        return False, f"defaultActionがSCMP_ACT_ALLOW(denylist方式)ではありません: {profile.get('defaultAction')!r}"

    syscalls = profile.get("syscalls")
    if not isinstance(syscalls, list) or not syscalls:
        return False, "syscalls配列が存在しないか空です。"

    denylist = set()
    for rule in syscalls:
        if rule.get("action") != "SCMP_ACT_ERRNO":
            return False, f"denylist方式に反する非ERRNOアクションが含まれています: {rule.get('action')!r}"
        denylist.update(rule.get("names", []))

    missing = _REQUIRED_CORE_DENYLIST - denylist
    if missing:
        return False, f"§CGで塞いだはずの核心的なシステムコールが、プロファイルから脱落しています(回帰): {sorted(missing)}"

    reintroduced = _FORBIDDEN_FROM_DENYLIST & denylist
    if reintroduced:
        return False, (
            f"execve/execveatがdenylistに再び含まれています(§CIで自己訂正した回帰の再発): {sorted(reintroduced)}。"
            f"これらを拒否すると、Docker/runcがコンテナのENTRYPOINTをexecveで起動する際に"
            f"コンテナ自体が起動できなくなる(実機で確認済み、GRIMOIRE.md §CI参照)。"
        )

    return True, "OK"


def _check_docker_run_references_profile() -> tuple:
    """`run_in_sandalphon()`のdocker run呼び出しが、実際に本プロファイル
    を`--security-opt seccomp=`で参照しているかを静的に確認する。"""
    path = ROOT / "src" / "sandalphon_jail.py"
    if not path.exists():
        return False, f"対象ファイルが見つかりません: {path}"
    text = path.read_text(encoding="utf-8-sig")
    if not re.search(r"--security-opt=seccomp=", text):
        return False, "run_in_sandalphon()のdocker run呼び出しに、--security-opt=seccomp=... が見つかりません(§CGの回帰)。"
    if "_SANDALPHON_SECCOMP_PROFILE" not in text:
        return False, "docker run呼び出しが、本プロファイルファイルへのパスを参照していないようです。"
    return True, "OK"


_RAW_KERNEL_CHECK_SCRIPT = r"""
import ctypes, json, os, socket, subprocess, sys

SCMP_ACT_ALLOW = 0x7fff0000
EPERM = 1

def _scmp_act_errno(errno):
    return 0x00050000 | (errno & 0x0000ffff)

def build_and_load_filter(names, errno=EPERM):
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]

    ctx = lib.seccomp_init(SCMP_ACT_ALLOW)
    if not ctx:
        raise RuntimeError("seccomp_init failed")
    unresolved = []
    for name in names:
        nr = lib.seccomp_syscall_resolve_name(name.encode())
        if nr < 0:
            unresolved.append(name)
            continue
        rc = lib.seccomp_rule_add(ctx, _scmp_act_errno(errno), nr, 0)
        if rc != 0:
            raise RuntimeError(f"seccomp_rule_add failed for {name}: rc={rc}")
    if unresolved:
        raise RuntimeError(f"unresolved syscalls: {unresolved}")
    rc = lib.seccomp_load(ctx)
    if rc != 0:
        raise RuntimeError(f"seccomp_load failed: rc={rc}")

def main():
    profile_path = sys.argv[1]
    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)
    denylist = [n for rule in profile["syscalls"] for n in rule["names"]]

    build_and_load_filter(denylist)
    results = {}

    try:
        pid = os.fork()
        # [自己発見・自己訂正 2026-10 §CG、実装中の自己レッドチームで検出]
        # fork()がdenylistで遮断されていない場合(本来のプロファイルでは
        # 常に遮断されるが、§CGの回帰テストはあえて遮断しない架空の
        # プロファイルを与えて本検査自体のFAIL検知能力を確認する)、ここで
        # os._exit()せずに単純にresultsへ記録するだけだと、子プロセスも
        # 親と全く同じコードを実行し続けてしまう。この子プロセスは、
        # subprocess.run(capture_output=True)が開いた標準出力・標準エラー
        # のパイプの書き込み端をforkによって複製して握ったまま残るため、
        # 親プロセス(このスクリプト)が先に終了しても、パイプの書き込み端
        # がまだ子プロセス側で開いたままとなり、呼び出し元の
        # subprocess.run()はEOFを検知できずcommunicate()で永久に待機し、
        # 最終的にTimeoutExpiredで初めて気づく、という形で実際に発生した
        # (本物のバグ。自分自身の回帰テストが検出した)。子プロセス側は
        # 直ちにos._exit()で終了し、パイプを継承したまま生き続けないよう
        # にし、親側はos.waitpid()で子の終了を待ってゾンビ化も防ぐ。
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        results["fork"] = "ALLOWED"
    except OSError as e:
        results["fork"] = "blocked" if e.errno == EPERM else f"wrong_errno:{e.errno}"

    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        results["socket"] = "ALLOWED"
    except OSError as e:
        results["socket"] = "blocked" if e.errno == EPERM else f"wrong_errno:{e.errno}"

    # [§CI注記] execve自体はこのdenylistにもはや含まれていない(§CIで
    # 自己訂正した通り、コンテナのENTRYPOINT起動を壊すため)。しかし
    # subprocess.run()は内部でfork系の呼び出しを経由してから execve
    # するため、fork/vfork/clone/clone3が拒否され続けている限り、
    # この呼び出しは「execveが拒否されたから」ではなく「新規プロセス
    # そのものを生成できないから」正しくEPERMで失敗するはずである。
    try:
        subprocess.run(["/bin/true"])
        results["new_process_via_subprocess"] = "ALLOWED"
    except OSError as e:
        results["new_process_via_subprocess"] = "blocked" if e.errno == EPERM else f"wrong_errno:{e.errno}"

    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    rc = libc.ptrace(0, 0, 0, 0)
    err = ctypes.get_errno()
    results["ptrace"] = "blocked" if (rc == -1 and err == EPERM) else f"NOT_BLOCKED:rc={rc},errno={err}"

    rc = libc.mount(b"none", b"/tmp", b"tmpfs", 0, None)
    err = ctypes.get_errno()
    results["mount"] = "blocked" if (rc == -1 and err == EPERM) else f"NOT_BLOCKED:rc={rc},errno={err}"

    results["getpid"] = "OK" if os.getpid() > 0 else "UNEXPECTED"
    tmpf = f"/tmp/dominions_raw_check_benign_{os.getpid()}.txt"
    with open(tmpf, "w") as f:
        f.write("benign write still works")
    with open(tmpf) as f:
        content = f.read()
    os.unlink(tmpf)
    results["open_write_read"] = "OK" if content == "benign write still works" else "UNEXPECTED"

    print(json.dumps(results))

if __name__ == "__main__":
    main()
"""

# [新設 2026-10 §CI] GRIMOIRE.md §CIで記録した自己発見の回帰
# (execveをdenylistに含めると、Docker/runcがコンテナのPID1へこの
# フィルタをロードした直後にENTRYPOINTをexecveする際、コンテナが
# 一度も起動できなくなっていた)を、二度と再発させないための直接
# 検証。重要なのは「execveが拒否されていないこと」そのものではなく
# ――「このフィルタが既にロードされた状態の、まさにこのプロセス
# 自身が、その場でexecveしてプロセス画像を入れ替えられること」で
# ある。これはDockerのPID1が置かれる状況と全く同じ形であり、
# fork()で子プロセスを作ってから子にexecveさせる形では、
# fork自体が拒否対象であるため本件の再検証にならない(フィルタの
# ロード後に、新しい子プロセスを作らずに、自分自身をそのまま
# execveで置き換える必要がある)。
_RAW_EXECVE_SELF_CHECK_SCRIPT = r"""
import ctypes, os, sys

SCMP_ACT_ALLOW = 0x7fff0000
EPERM = 1

def _scmp_act_errno(errno):
    return 0x00050000 | (errno & 0x0000ffff)

def build_and_load_filter(names, errno=EPERM):
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]

    ctx = lib.seccomp_init(SCMP_ACT_ALLOW)
    if not ctx:
        raise RuntimeError("seccomp_init failed")
    for name in names:
        nr = lib.seccomp_syscall_resolve_name(name.encode())
        if nr < 0:
            continue
        rc = lib.seccomp_rule_add(ctx, _scmp_act_errno(errno), nr, 0)
        if rc != 0:
            raise RuntimeError(f"seccomp_rule_add failed for {name}: rc={rc}")
    rc = lib.seccomp_load(ctx)
    if rc != 0:
        raise RuntimeError(f"seccomp_load failed: rc={rc}")

if __name__ == "__main__":
    import json
    profile_path = sys.argv[1]
    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)
    denylist = [n for rule in profile["syscalls"] for n in rule["names"]]
    build_and_load_filter(denylist)
    # フィルタをロードした直後、新しい子プロセスを一切作らずに、
    # まさにこの自分自身のプロセス画像を /bin/true へ置き換える。
    # これがDocker/runcがコンテナのPID1に対して行う操作と全く同じ形
    # である。execveが拒否されていれば、ここでOSErrorが飛ぶ。
    os.execve("/bin/true", ["/bin/true"], os.environ)
"""


def _check_execve_after_filter_load_still_works() -> tuple:
    """GRIMOIRE.md §CIの回帰(execveをdenylistに含めるとコンテナ自体が
    起動できなくなる)が再発していないかを、Dockerを使わず直接確認する。
    `_check_raw_kernel_enforcement()`とは独立した検証である――そちらは
    「危険なシステムコールが遮断されているか」を見るが、本検査は逆に
    「フィルタロード後も、まさにこのプロセス自身によるexecveでの
    自己置換(=コンテナのPID1がENTRYPOINTを起動する状況そのもの)が
    壊れていないか」を見る。

    戻り値: ("PASS"|"FAIL"|"INCONCLUSIVE", detail)
    """
    try:
        ctypes.CDLL("libseccomp.so.2")
    except OSError as e:
        return "INCONCLUSIVE", f"libseccomp.so.2がこの環境に見つからないため、本検証を実施できません: {e}"

    if not os.path.exists("/bin/true"):
        return "INCONCLUSIVE", "/bin/trueがこの環境に見つからないため、本検証を実施できません。"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(_RAW_EXECVE_SELF_CHECK_SCRIPT)
        script_path = tf.name

    try:
        proc = subprocess.run(
            [sys.executable, script_path, str(_PROFILE_PATH)],
            capture_output=True, text=True, timeout=15,
        )
    finally:
        # [正直な注記] `_check_raw_kernel_enforcement()`と同じ理由により、
        # 一時スクリプトの削除はあくまで後始末であり、本検査の正しさ
        # (execveによる自己置換が機能しているか)そのものには関わらない。
        # 開発環境自身の一時領域が外部要因で不安定な場合(既に消えている
        # 場合)にまでFileNotFoundErrorで本検査全体を失敗させるのは
        # 過剰であるため、ここも同様に寛容に扱う。
        try:
            os.unlink(script_path)
        except FileNotFoundError:
            pass

    if proc.returncode != 0:
        return "FAIL", (
            f"seccompフィルタのロード後、このプロセス自身がexecveで"
            f"自己置換(=コンテナのPID1がENTRYPOINTを起動する状況)を"
            f"行おうとして失敗しました(§CIの回帰の再発): "
            f"returncode={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    return "PASS", "seccompフィルタのロード後も、execveによる自己置換(コンテナ起動相当の操作)が正常に成功することを確認しました。"


def _check_raw_kernel_enforcement() -> tuple:
    """Dockerを一切使わず、libseccomp(C ABI)への直接ctypes呼び出しで、
    実際のプロファイルJSONと同じdenylistをこの実機のカーネルへロード
    し、denylist上の各システムコールが本当にEPERMで拒否され、良性の
    操作は引き続き成功することを確認する。Dockerデーモン・コンテナ
    レジストリのいずれにも依存しないため、§CFと異なりこの調査環境でも
    常に実行可能なはずである。

    戻り値: ("PASS"|"FAIL"|"INCONCLUSIVE", detail)
    """
    try:
        ctypes.CDLL("libseccomp.so.2")
    except OSError as e:
        return "INCONCLUSIVE", f"libseccomp.so.2がこの環境に見つからないため、生カーネル検証を実施できません: {e}"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(_RAW_KERNEL_CHECK_SCRIPT)
        script_path = tf.name

    try:
        proc = subprocess.run(
            [sys.executable, script_path, str(_PROFILE_PATH)],
            capture_output=True, text=True, timeout=15,
        )
    finally:
        # [正直な注記] 一時スクリプトの削除はあくまで後始末であり、本検査
        # の正しさ(denylistが実際に機能しているか)そのものには関わらない。
        # 既に消えていた場合(他プロセスによる一時領域の掃除等)にまで
        # FileNotFoundErrorで本検査全体を失敗させるのは過剰であるため、
        # 寛容に扱う。
        try:
            os.unlink(script_path)
        except FileNotFoundError:
            pass

    if proc.returncode != 0:
        return "FAIL", f"生カーネル検証スクリプト自体が異常終了しました: stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        results = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as e:
        return "FAIL", f"生カーネル検証スクリプトの出力を解析できませんでした: {e}: stdout={proc.stdout!r} stderr={proc.stderr!r}"

    denied_checks = ["fork", "socket", "new_process_via_subprocess", "ptrace", "mount"]
    not_blocked = [k for k in denied_checks if results.get(k) != "blocked"]
    if not_blocked:
        return "FAIL", f"以下のシステムコールが、プロファイルをロードしたにもかかわらず実際には遮断されませんでした: {[(k, results.get(k)) for k in not_blocked]}"

    benign_checks = ["getpid", "open_write_read"]
    broken_benign = [k for k in benign_checks if results.get(k) != "OK"]
    if broken_benign:
        return "FAIL", f"denylistに含まれないはずの良性の操作が、誤って遮断・破壊されています(誤検知): {[(k, results.get(k)) for k in broken_benign]}"

    return "PASS", "libseccompでプロファイルと同じdenylistを実機のカーネルへロードし、fork/socket/ptrace/mountが全てEPERMで拒否され(新規プロセス生成は一切不可能)、execveを要しないgetpid・ファイルの読み書きは引き続き正常に動作することを確認しました。"


def _check_docker_dynamic_if_possible() -> tuple:
    """可能であれば、実際にDockerコンテナへ本プロファイルを適用し、
    コンテナ内でもos.fork()等が遮断されることまで確認する。この調査
    環境ではコンテナレジストリへの到達が遮断されているため、§CFと
    同様にINCONCLUSIVEとなることが予想されるが、GitHub Actions等、
    実際にイメージを取得できる環境では本当にPASS/FAILが判定される。

    戻り値: ("PASS"|"FAIL"|"INCONCLUSIVE", detail)
    """
    sys.path.insert(0, str(ROOT / "src"))
    import sandalphon_jail as sj

    available, reason = sj.check_docker_available()
    if not available:
        return "INCONCLUSIVE", f"Dockerデーモン自体が利用不可のため、コンテナ内での動的検証を実施できません: {reason}"

    try:
        sj._ensure_image_built()
    except subprocess.SubprocessError as e:
        return "INCONCLUSIVE", f"隔離結界イメージの取得・構築ができないため、この環境では動的検証を実施できません(ネットワーク許可一覧によるコンテナレジストリ遮断が原因である可能性が高い): {e}"

    result = sj.run_in_sandalphon("import os, sys\ntry:\n    os.fork()\n    print('FORK_SUCCEEDED')\nexcept OSError:\n    print('FORK_BLOCKED')\n")
    if not result["executed"]:
        return "INCONCLUSIVE", f"コンテナの実行自体に到達できませんでした: {result}"
    if "FORK_BLOCKED" in result["stdout"]:
        return "PASS", "実際のSandalphonコンテナ内で、os.fork()がseccompプロファイルにより遮断されることを確認しました。"
    if "FORK_SUCCEEDED" in result["stdout"]:
        return "FAIL", f"seccompプロファイルを適用したにもかかわらず、コンテナ内でos.fork()が成功してしまいました(回帰): {result}"
    return "FAIL", f"想定した出力が得られませんでした: {result}"


def main():
    ok, detail = _check_profile_json_is_well_formed()
    if not ok:
        report_fail(NAME, f"seccompプロファイルのdenylistが後退しています(§CGの回帰): {detail}")
        return

    ok, detail = _check_docker_run_references_profile()
    if not ok:
        report_fail(NAME, f"Sandalphon隔離結界がseccompプロファイルを参照していません(§CGの回帰): {detail}")
        return

    status, detail = _check_raw_kernel_enforcement()
    if status == "FAIL":
        report_fail(NAME, f"生カーネル検証で、seccompプロファイルが実際には機能していないことが判明しました: {detail}")
        return
    if status == "INCONCLUSIVE":
        report_inconclusive(NAME, f"静的検証はPASSしましたが、生カーネル検証を実施できませんでした: {detail}")
        return
    raw_kernel_detail = detail

    status, detail = _check_execve_after_filter_load_still_works()
    if status == "FAIL":
        report_fail(NAME, f"seccompフィルタのロード後、execveによる自己置換(コンテナ起動相当)が壊れています(§CIの回帰の再発): {detail}")
        return
    if status == "INCONCLUSIVE":
        report_inconclusive(NAME, f"ここまではPASSしましたが、execve自己置換の検証を実施できませんでした: {detail}")
        return
    execve_self_check_detail = detail

    docker_status, docker_detail = _check_docker_dynamic_if_possible()
    if docker_status == "FAIL":
        report_fail(NAME, f"実際のSandalphonコンテナ内でseccompプロファイルが機能していません: {docker_detail}")
        return

    if docker_status == "INCONCLUSIVE":
        report_inconclusive(
            NAME,
            f"静的検証・生カーネル検証(libseccomp直接ロード)・execve自己置換検証はPASSしましたが、実際の"
            f"Dockerコンテナ内での動的検証はこの環境では実施できませんでした。生カーネル検証の結果: "
            f"{raw_kernel_detail} / execve自己置換検証: {execve_self_check_detail} / コンテナ検証: {docker_detail}",
        )
        return

    report_pass(
        NAME,
        f"seccompプロファイルのdenylist・Sandalphonからの参照・生カーネルへの直接ロード・execveによる"
        f"コンテナ起動相当の自己置換・実際のコンテナ内実行の全てで、fork/socket/ptrace/mount等の危険な"
        f"システムコールが遮断されつつ、コンテナの起動そのものに必要なexecveと良性の操作は引き続き"
        f"正常に動作することを確認しました。",
    )


if __name__ == "__main__":
    main()
