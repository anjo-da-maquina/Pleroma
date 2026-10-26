import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "ゼラキエルの産まれの検問 (Zerachiel's Birth-Watch - 深層保護のプロセス生成迂回検知)"

# [新設 2026-10 §CC] 実際に発見した具体例: `maquina_gatekeeper.py`の
# `ultimate_audit_hook`("深層保護")は、新しいOSプロセスの生成を遮断
# する目的で`forbidden`集合に"subprocess.Popen"・"os.system"・
# "os.exec"・"os.posix_spawn"の4つのaudit eventを含めていた。しかし
# `os.fork()`は、これらのいずれも経由せず、専用の全く別のaudit event
# "os.fork"を発火させてプロセスを生成できるため、`forbidden`集合に
# 一度も一致せず、封鎖中でも完全に素通りしていた(実機で確認済み:
# `set_sanctuary_sealed(True)`の状態でも、`os.fork()`が例外無しに
# 成立することを確認した)。
#
# [別個の防御層との非対称性] 本リポジトリには、本ファイルとは別個に
# 独立して存在するもう一つのランタイム防御層`sefer/__init__.py`の
# `_HARD_DENY_EVENTS`があり、そちらは最初から"os.fork"/"os.forkpty"を
# 含んでいた。つまり同じ種類の脅威(fork()によるプロセス生成)に対して、
# 一方の防御層は既に対応済みで、もう一方(本ファイルの
# `ultimate_audit_hook`)だけが未対応のまま残っていた――§CAの
# "socket.sendto"と同じ構造の非対称性である。forbidden集合に
# "os.fork"・"os.forkpty"を追加した修正を、継続的に再検証する。
#
# [一般化の方針] §BW・§CA・§CBと同じ構造の欠陥――禁止したい意図
# (「新しいプロセスを起動させない」)は変わらないのに、実装が特定の
# 複数のAPIにしか結び付けられていなかったため、同じ目的を達成できる
# 別のAPI(fork)を使うだけで迂回されてしまう。本天使は、
# `ultimate_audit_hook`の実装詳細を静的に解析するのではなく、実際に
# 登録し、封鎖状態で既知のプロセス生成迂回経路(`os.fork()`)を実際に
# 発火させて、正しく遮断されることを継続的に検証する回帰連戦である。
#
# [正直な注記: 本検査の限界] (1) 本天使が検証するのは`os.fork()`という
# 既知の具体的な経路のみであり、`os.forkpty()`は同じ修正でカバーされて
# いるはずだが、本天使のCHECKSには直接の実行確認を含めていない
# (子プロセス生成を伴うテストをさらに増やすことによる、CI環境での
# プロセス管理上の複雑さ・不安定化のリスクを避けるため、意図的に
# `os.fork()`一本に絞った最小限の実証に留めている――これは将来、
# `os.forkpty()`個別の直接検証を追加する余地が残っていることを正直に
# 記す)。(2) 本天使が検証する深層保護は、本リポジトリ全体のゼロ
# トラストアーキテクチャの一層(defense in depth)に過ぎず、唯一の
# 防衛線ではない――Docker等によるOSレベルのプロセス・ネットワーク隔離
# が一次防衛線であることは、`cassiels_veil`関連の既存のGRIMOIRE記述が
# 既に明記している前提と同じである。

sys.path.insert(0, str(ROOT))


def _check_fork_is_blocked_while_sealed() -> tuple:
    """封鎖中にos.fork()が正しく遮断されるかを確認する。
    戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    mg.set_sanctuary_sealed(True)
    try:
        pid = os.fork()
        if pid == 0:
            # [正直な注記] ここに処理が渡った時点で既に本検査は失敗して
            # いる(親側でLossOfAtaraxiaが発生しなかった)。子プロセスが
            # 検査プロセスの状態を引き継いで二重に動作するのを避けるため、
            # 即座に終了させる。os._exit()は標準出力バッファのflushを
            # 行わないため(§BQ/§BRで発見済みの構造と同一)、事前に明示的
            # にflushしておく。
            sys.stdout.flush()
            os._exit(0)
        else:
            os.waitpid(pid, 0)
        return False, "封鎖中にos.fork()によるプロセス生成が遮断されなかった"
    except mg.LossOfAtaraxia:
        return True, "OK"
    finally:
        mg.set_sanctuary_sealed(False)


def _check_fork_is_allowed_when_unsealed() -> tuple:
    """[誤検知防止] 封鎖していない通常時は、os.fork()が誤って遮断され
    ないかを確認する。戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    if mg.is_sanctuary_sealed():
        return False, "前提条件の異常: 検査開始時点で既に封鎖状態になっている"
    try:
        pid = os.fork()
        if pid == 0:
            # [正直な注記] 同上。os._exit()前に明示的にflushしておく。
            sys.stdout.flush()
            os._exit(0)
        else:
            _, status = os.waitpid(pid, 0)
            if not (os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0):
                return False, "子プロセスが正常終了しなかった(fork自体の異常)"
        return True, "OK"
    except mg.LossOfAtaraxia:
        return False, "封鎖していないのにos.fork()が誤って遮断された"


CHECKS = [
    ("maquina_gatekeeper.ultimate_audit_hook: os.fork遮断", _check_fork_is_blocked_while_sealed),
    ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止", _check_fork_is_allowed_when_unsealed),
]


def run_battery():
    """`ultimate_audit_hook`に対し、既知のプロセス生成迂回経路を実際に
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
            f"深層保護のプロセス生成遮断に、少なくとも1つの既知の"
            f"迂回経路が再発しています(§CCの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "封鎖中のos.fork()によるプロセス生成が正しく遮断され、かつ"
        "非封鎖時には誤って遮断されないことを確認しました。",
    )


if __name__ == "__main__":
    main()
