import sys
import os
import ast
import base64
import codecs
import socket
import ssl
import json
import re
import time
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import List, Any, Set, Dict

class LossOfAtaraxia(BaseException):
    pass

def _log_violation_to_chain(event: str, details: dict):
    # [脆弱性修正 2026-10] 以前はここに独自のSHA-256ハッシュ連鎖の実装を
    # 直接持っていたが、これは秘密鍵を用いない単純なハッシュ連鎖に過ぎず、
    # ファイルへの書き込み権限を持つ攻撃者が改ざんを検知されずに行えて
    # しまう脆弱性があった(sefer/audit_chain.py のSignedAuditChainクラスの
    # docstring、GRIMOIRE.md §AE参照)。また、本関数とSignedAuditChainとで
    # 同じフォーマットのハッシュ連鎖ロジックが二重実装されており、片方だけ
    # 修正すると両者が食い違って`verify_integrity()`が壊れるリスクもあった。
    # 唯一の実装であるSignedAuditChain(鍵付きHMAC-SHA256版)に委譲するよう
    # 修正した。
    try:
        from .audit_chain import SignedAuditChain
    except ImportError:
        # パッケージとしてではなく単体で読み込まれた場合のフォールバック。
        from audit_chain import SignedAuditChain
    truncated_details = {k: str(v)[:200] for k, v in details.items()}
    try:
        SignedAuditChain(log_path="sefer/audit_chain.jsonl").record(event, truncated_details)
    except Exception:
        pass

_active_stack = []

_STDLIB_ALLOWED_READ_DIRS = [Path(p).resolve() for p in {sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix} if p]

class Sanctum:
    def __init__(self, allowed_dirs=None, allowed_hosts=None, restrict_reads=False):
        """
        allowed_dirs:   書き込み・破壊的操作を許可するディレクトリ一覧。
        allowed_hosts:  通信を許可するホスト一覧。
        restrict_reads: True にすると、allowed_dirs（および Python 本体の
                         標準ライブラリ/site-packages）以外のファイル読み取りも
                         ブロックする「読み取りゼロトラスト」モード。
                         デフォルトは False（既存動作との後方互換のため）。
                         [脆弱性修正 2026-10] 以前は読み取りが完全に無制限だった。
        """
        # [脆弱性修正 2026-10 §AV] 以前は、子スコープの`allowed_dirs`絞り込みに
        # `any(d == pd or d.is_relative_to(pd) for pd in parent_dirs) or
        #  any(pd == d or pd.is_relative_to(d) for pd in parent_dirs)` という、
        # 二つの条件をORで結合した判定を使っていた。前半(`d`が`pd`の配下)は
        # 正しい「子は親の範囲内にしか narrow できない」判定だが、後半
        # (`pd`が`d`の配下、つまり`d`が`pd`の\*\*祖先\*\*)は、子が親の
        # ディレクトリより\*\*広い\*\*祖先ディレクトリを指定した場合にも
        # 真になってしまう。例えば親が`allowed_dirs=["jail_workspace"]`で
        # ネストした子が`allowed_dirs=["/"]`を指定すると、"/"は
        # "jail_workspace"の祖先(あらゆる絶対パスの祖先は"/")であるため
        # 後半の条件が真になり、子の`allowed_dirs`が`["/"]`(ファイル
        # システム全体)に\*\*昇格\*\*してしまう重大な脱獄脆弱性だった。
        # 実機検証済み: `with Sanctum(allowed_dirs=["jail_workspace"]):`の
        # 内側で`with Sanctum(allowed_dirs=["/"]):`を開き、`/tmp/`配下への
        # 書き込みが実際に成功することを確認した。ネストしたSanctumは
        # 「親より狭くすることしかできない」のが設計意図であるべきなので、
        # 後半の祖先方向の判定を削除し、前半(子は親の配下でなければ
        # 棄却される)のみを残した。
        new_dirs = [Path(d).resolve() for d in (allowed_dirs or [])]
        new_hosts = set(allowed_hosts or [])

        if _active_stack:
            parent = _active_stack[-1]
            if allowed_dirs is not None:
                parent_dirs = parent["allowed_dirs"]
                self.allowed_dirs = [
                    d for d in new_dirs
                    if any(d == pd or d.is_relative_to(pd) for pd in parent_dirs)
                ]
            else:
                self.allowed_dirs = parent["allowed_dirs"]

            if allowed_hosts is not None:
                self.allowed_hosts = new_hosts.intersection(parent["allowed_hosts"])
            else:
                self.allowed_hosts = parent["allowed_hosts"]

            # restrict_reads は一度有効化したら、子スコープで無効化できない（降格禁止）
            self.restrict_reads = restrict_reads or parent.get("restrict_reads", False)
        else:
            self.allowed_dirs = new_dirs
            self.allowed_hosts = new_hosts
            self.restrict_reads = restrict_reads

        self.policy = {
            "allowed_dirs": self.allowed_dirs,
            "allowed_hosts": self.allowed_hosts,
            "restrict_reads": self.restrict_reads,
        }

    def __enter__(self):
        _active_stack.append(self.policy)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if _active_stack:
            _active_stack.pop()

def _is_guard_active() -> bool:
    return len(_active_stack) > 0

def _get_current_policy() -> dict:
    if _active_stack:
        return _active_stack[-1]
    return {"allowed_dirs": [], "allowed_hosts": set(), "restrict_reads": False}

def _is_path_allowed(target_path, allowed_dirs) -> bool:
    try:
        target = Path(target_path).resolve()
        for d in allowed_dirs:
            resolved_d = Path(d).resolve()
            try:
                if target == resolved_d or target.is_relative_to(resolved_d):
                    return True
            except ValueError:
                pass
            # [脆弱性修正 2026-10] 以前はこのフォールバック文字列比較で
            # .lower() により大文字小文字を無視して比較していたため、
            # allowed_dirsと大文字小文字が異なるだけの「別の実ディレクトリ」
            # (例: allowed_dirs=["jail_workspace"]に対し実際に存在する
            # "JAIL_WORKSPACE"という完全に別のディレクトリ)への書き込み・
            # 破壊的操作が許可されてしまう脆弱性があった(Linux等の大文字
            # 小文字を区別するファイルシステムで実機検証済み: Sanctum配下で
            # allowed_dirs外の"JAIL_WORKSPACE_repro"ディレクトリへの書き込み
            # がブロックされずに通過することを確認)。本来この文字列比較は
            # パス区切り文字(バックスラッシュ→スラッシュ)の正規化のみを
            # 目的としており、大文字小文字の無視は意図した挙動ではない。
            # 大文字小文字は元の文字列のまま厳密に比較するよう修正した。
            t_str = str(target).replace("\\", "/")
            d_str = str(resolved_d).replace("\\", "/")
            if t_str == d_str or t_str.startswith(d_str + "/"):
                return True
        return False
    except Exception:
        return False

_HARD_DENY_EVENTS = {
    "os.system", "os.popen", "os.spawn", "os.exec", "os.fork", "os.forkpty",
    "os.startfile", "pty.spawn", "subprocess.Popen", "_thread.start_new_thread",
    "ctypes.dlopen", "ctypes.CDLL", "ctypes.PyDLL", "sys.settrace", "sys.setprofile",
    "marshal.loads", "pickle.find_class"
}

# [脆弱性修正 2026-10 §BJ] `_michael_absolute_defense`の2(ソケット検査)・
# 4(デフォルト拒否)は、以下のイベント名を常に無条件で通過させる
# (`pass`してこのブロック自体を`return`で抜ける)。これらは
# `sefer/raziel_ledger.json`(Razielの台帳、Armageddonの自己対戦が発見し
# 人間が承認した新しい禁止イベントを反映する動的な仕組み)がどれだけ
# "banned_events"に含めても、本関数の5(Razielの台帳の enforcement)自体に
# 到達する前に必ずこの時点で無条件に許可されて`return`するため、*絶対に*
# 禁止できない。元々この2つの集合はそれぞれの検査ブロック内にリテラルの
# `{...}`として個別に書かれていたため、一方だけ変更して他方が取り残される
# ドリフトのリスクがあった(GRIMOIRE.md §Mと同種)ため、ここに統合した上で
# 各検査ブロックから参照する。
#
# `tartarus/armageddon_core.py`の`validate_banned_event()`は、この集合を
# 用いて「台帳に追加しても構造的に絶対に効果が無い」イベント名の承認提案を
# 事前に拒否する(詳細はGRIMOIRE.md §BJ参照)。
ALWAYS_PASSTHROUGH_AUDIT_EVENTS = frozenset({
    "os.stat", "os.listdir", "os.getcwd", "os.path",
    "socket.getaddrinfo", "socket.socket", "socket.__init__",
    # [脆弱性修正 2026-10 §CO追記] "socket.socket"/"socket.__init__"は、
    # このコメントが書かれた時点で想定していたイベント名だったと見られるが、
    # 実機(CPython 3.13)で実際に`sys.addaudithook`で捕捉したところ、
    # ソケット生成時に本当に発火するイベント名は"socket.__new__"であり、
    # この一覧に含まれていなかったことを確認した。その結果、
    # `allowed_hosts`を指定してSanctumを起動していても、**ソケットの
    # 生成そのもの**(`socket.socket(...)`、ホスト情報を一切持たない)が
    # 無条件に`_trigger_violation`されてしまい、許可ホストへの接続を含む
    # 正当な通信フローが、接続を試みる前の時点で常に失敗する
    # fail-closed方向の誤検知(過剰ブロック)になっていたことを実機で
    # 確認した(セキュリティホールではなく、allowed_hosts機能そのものが
    # 事実上使えなくなっていたという可用性側の欠陥)。ホストの許可判定は、
    # 実際にホスト情報を伴って発火する"socket.connect"等で引き続き
    # 正しく行われるため、生成イベント自体は安全に通過させてよい。
    "socket.__new__",
})

# Pythonの audit event 名として妥当な形式のみ許可（例: "os.system", "subprocess.Popen"）。
# tartarus/armageddon_core.py / angels/_common.py と同一の正規表現。
VALID_EVENT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")

# [脆弱性修正 2026-10] `tartarus/armageddon.py`(Lucifer vs Sefer自己対戦)が
# 発見し、`tools/promote_ledger_seal.py`で人間が明示的に承認した新たな禁止
# イベント(`sefer/raziel_ledger.json`の`banned_events`)は、これまで
# `_michael_absolute_defense`から一切読み込まれておらず、承認してもシステム
# の実際の防御には何ら反映されない「学習したつもりになっているだけ」の状態
# だった(`angels/raziel_auditor.py`はファイルのスキーマ検証のみで、実際に
# 読み込まれ enforce されているかは検証していなかった)。
#
# [設計上の制約・安全性の確認] 本番の`sefer/raziel_ledger.json`には既定で
# "os.remove"・"os.rmdir"・"os.rename"・"socket.connect"のように、Michael
# が既に個別の条件付きチェック(allowed_dirs/allowed_hosts。下記の各`return`
# 文)で扱っているイベント名が含まれている。これらを本関数の先頭で無条件の
# 絶対拒否として扱うと、AI自身のjail_workspace配下での正当なファイル操作や、
# ローカルOllamaサーバーへの正当な接続まで一律遮断してしまう重大な機能破壊
# になる(実機で確認済み)。そのため、本チェックは既存の各条件付きチェックが
# 既に`return`で処理し終えた後に到達する関数の\*\*最後\*\*でのみ適用する。
# これにより、既存の条件付きチェックで既にカバーされているイベント名
# (os.remove等)は従来通りの挙動(allowed_dirs内なら許可)を維持したまま、
# どのカテゴリにも当てはまらない\*\*未知の新しい脱走経路\*\*(Armageddonが
# 今後発見し人間が承認した、現行のどの固定カテゴリにも該当しないイベント)
# だけを新たに絶対拒否できるようにする。ファイルのmtimeをキャッシュキーに
# 使い、audit hookの頻繁な呼び出しごとに毎回ファイルを読み直すことによる
# 性能劣化を避けつつ、人間の承認がプロセス再起動不要で即座に反映されるよう
# にする。
_RAZIEL_LEDGER_PATH = Path("sefer/raziel_ledger.json")
_dynamic_banned_events_cache = {"mtime": None, "events": frozenset()}


def _load_dynamic_banned_events() -> frozenset:
    try:
        mtime = _RAZIEL_LEDGER_PATH.stat().st_mtime
    except OSError:
        return frozenset()
    if _dynamic_banned_events_cache["mtime"] == mtime:
        return _dynamic_banned_events_cache["events"]
    try:
        with open(_RAZIEL_LEDGER_PATH, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        events = frozenset(
            e for e in ledger.get("banned_events", [])
            if isinstance(e, str) and VALID_EVENT_NAME_RE.match(e)
        )
    except Exception:
        events = frozenset()
    _dynamic_banned_events_cache["mtime"] = mtime
    _dynamic_banned_events_cache["events"] = events
    return events


_hook_state = threading.local()

def _michael_absolute_defense(event: str, args: tuple):
    if getattr(_hook_state, 'in_hook', False):
        return

    if not _is_guard_active():
        return

    _hook_state.in_hook = True
    try:
        policy = _get_current_policy()

        # 1. ハードデニーチェックの精密化（os.execの誤爆防止）
        for deny in _HARD_DENY_EVENTS:
            # プレフィックス一致（os.execvなどをブロックしつつ、単体のexecは通す）
            if event == deny or event.startswith(deny):
                _trigger_violation(event, args, f"Hard-denied event '{event}' blocked.")

        # 2. ソケット通信検査
        if "socket" in event or event.startswith("socket"):
            if event in ALWAYS_PASSTHROUGH_AUDIT_EVENTS:
                pass
            else:
                target_host = None
                for arg in args:
                    if isinstance(arg, tuple) and len(arg) >= 2 and isinstance(arg[0], str):
                        target_host = arg[0]
                        break
                    elif isinstance(arg, str) and ("." in arg or ":" in arg):
                        target_host = arg
                        break

                if not target_host:
                    _trigger_violation(event, args, "Unauthorized network connection to target host.")

                allowed_hosts = policy.get("allowed_hosts", set())
                if target_host not in allowed_hosts:
                    _trigger_violation(event, args, f"Unauthorized network connection to '{target_host}'.")
            return

        # 2.5. [脆弱性修正 2026-10 §CB] mmapによるfd書き込みバイパス対策
        # -----------------------------------------------------------
        # 発見: 「fd事前オープンによる書き込みバイパス対策」(459行目
        # 周辺、`_guarded_os_write`等)は os.write/os.pwrite/os.writev/
        # os.pwritev の4系統のみをラップしていた。しかし
        # `mmap.mmap(fd, length, access=mmap.ACCESS_WRITE)` で、
        # 「Sanctumに入る『前』に確保しておいた書き込み用fd」をメモリに
        # マップし、`mm[0:N] = b'...'` のようなスライス代入をするだけで、
        # os.write系APIを一切経由せずにファイルへ書き込める。これは
        # os.write系とは別個の、CPythonの正式な監査イベント
        # "mmap.__new__"を発生させるにもかかわらず、本関数はこの
        # イベントを一度も検査していなかった(ハードデニー・ソケット・
        # open/os.open・削除系・リネーム系のいずれにも一致せず、さらに
        # 後述4のデフォルト拒否の`monitored_namespaces`にも"mmap."が
        # 含まれていないため、完全に素通りしていた。実機検証済み:
        # allowed_dirs外のファイルについて、Sanctumに入る前に確保した
        # fdをmmapし、スライス代入で書き込む攻撃が、例外を一切発生
        # させずに成功することを確認した)。
        #
        # [正直な注記] "mmap.__new__"イベントのargs[2](access)は、
        # `access=`キーワードで構築した場合は要求した値(ACCESS_WRITE=2
        # 等)を正しく報告するが、Unix系の`prot=`/`flags=`キーワードで
        # 構築した場合は、実際にPROT_WRITEを要求していても常に0を報告
        # することを実機で確認した(匿名mmap `mmap.mmap(-1, 100)`と
        # 全く同じ値になり、両者はargs[2]だけでは判別不能)。そのため
        # access値は書き込み意図の判定には信頼できない。本修正は宣言
        # されたaccess値を一切信用せず、fd経由で解決した実体パスのみに
        # 基づいて判定する、既存の`_check_fd_write_allowed`と同じ
        # fail-closed方針を採用する: 実ファイルを指すfdでの非匿名mmapは
        # access値に関わらず一律allowed_dirs内かどうかで判定する
        # (匿名マッピング`fileno=-1`は実体ファイルを持たないため常に
        # 許可する)。[既知の限界] これは宣言上「読み取り専用」の
        # mmapであっても、allowed_dirs外のファイルに対しては一律遮断
        # するという意味で、os.open/openの読み取り検査(restrict_reads
        # 時のみ遮断)より厳しい。これはaccess値が信頼できない以上、
        # 安全側に倒した意図的な設計判断である。
        if event == "mmap.__new__":
            fileno = args[0] if args else -1
            if isinstance(fileno, int) and fileno >= 0 and fileno not in _WHITELISTED_FDS:
                path = _resolve_fd_path(fileno)
                if path is not None and not _is_path_allowed(path, policy["allowed_dirs"]):
                    _trigger_violation(
                        event, args,
                        f"Unauthorized mmap access to '{path}' (fd={fileno}, pre-opened handle bypass via mmap)."
                    )
            return

        # 3. ファイル書き込み検査 (open / os.open)
        if event == "open":
            path = args[0]
            mode = args[1] if len(args) > 1 else "r"
            is_write_mode = isinstance(mode, str) and any(m in mode for m in ("w", "a", "+", "x", "r+"))
            if is_write_mode:
                if not _is_path_allowed(path, policy["allowed_dirs"]):
                    _trigger_violation(event, args, f"Unauthorized write access to '{path}'.")
            elif policy.get("restrict_reads"):
                # [脆弱性修正 2026-10] 以前は読み取りを一切検査していなかった。
                if not (_is_path_allowed(path, policy["allowed_dirs"]) or
                        _is_path_allowed(path, _STDLIB_ALLOWED_READ_DIRS)):
                    _trigger_violation(event, args, f"Unauthorized read access to '{path}'.")
            return

        if event == "os.open":
            path = args[0]
            flags = args[1] if len(args) > 1 else 0
            is_write = (flags & 1) or (flags & 2) or (flags & 512) or (flags & 1024) or (flags & 64)
            if is_write:
                if not _is_path_allowed(path, policy["allowed_dirs"]):
                    _trigger_violation(event, args, f"Unauthorized os.open write access to '{path}'.")
            elif policy.get("restrict_reads"):
                if not (_is_path_allowed(path, policy["allowed_dirs"]) or
                        _is_path_allowed(path, _STDLIB_ALLOWED_READ_DIRS)):
                    _trigger_violation(event, args, f"Unauthorized os.open read access to '{path}'.")
            return

        if event in {"os.remove", "os.rmdir", "os.unlink", "os.truncate", "os.chmod", "os.chown", "os.mkdir", "os.utime"}:
            if args and not _is_path_allowed(args[0], policy["allowed_dirs"]):
                _trigger_violation(event, args, f"Unauthorized destructive access to '{args[0]}'.")
            return

        if event in {"os.rename", "os.replace"}:
            src = args[0] if len(args) > 0 else None
            dst = args[1] if len(args) > 1 else None
            if src and not _is_path_allowed(src, policy["allowed_dirs"]):
                _trigger_violation(event, args, f"Unauthorized rename source '{src}'.")
            if dst and not _is_path_allowed(dst, policy["allowed_dirs"]):
                _trigger_violation(event, args, f"Unauthorized rename destination '{dst}'.")
            return

        # 4. デフォルト拒否 (Default-Deny)
        monitored_namespaces = ("os.", "subprocess.", "socket.", "pty.", "ctypes.", "shutil.", "fcntl.", "_thread.")
        if any(event.startswith(ns) or ns[:-1] in event for ns in monitored_namespaces):
            if event not in ALWAYS_PASSTHROUGH_AUDIT_EVENTS:
                _trigger_violation(event, args, f"Default-deny blocked unwhitelisted system event '{event}'.")
            return

        # 5. [脆弱性修正 2026-10] Armageddonの自己対戦が発見し、人間が承認した
        # 未知の脱走経路(sefer/raziel_ledger.json)を、ここで初めて enforce する。
        # 上記1〜4のいずれかで既に`return`済みのイベント(os.remove等、既存の
        # 条件付きチェックで処理されるもの)はこの行に到達しないため、既存の
        # allowed_dirs/allowed_hosts に基づく挙動は変わらない。ここに到達する
        # のは、どの既存カテゴリにも該当しなかった(=これまで一切チェックされ
        # ていなかった)イベントのみであり、そのうち raziel_ledger.json で
        # 承認済みのものだけを絶対拒否する。
        if event in _load_dynamic_banned_events():
            _trigger_violation(event, args, f"Raziel's Ledger(学習済みの禁止イベント)が'{event}'を遮断しました。")
    finally:
        _hook_state.in_hook = False

def _trigger_violation(event: str, args: tuple, message: str):
    _log_violation_to_chain(event, {"args": args, "message": message})
    raise LossOfAtaraxia(f"[Sefer] Tripwire: {message}")

@dataclass
class Finding:
    rule_id: str
    severity: str
    lineno: int
    message: str

_SHIELD_RULES_PATH = Path("shield_rules.json")
_dynamic_shield_rules_cache = {"mtime": None, "modules": frozenset(), "funcs": frozenset()}


def _load_dynamic_shield_rules() -> tuple:
    """
    [脆弱性修正 2026-10] `tools/promote_shield_seal.py`で人間が承認した
    外部脅威インテリジェンス(`shield_rules.json`の`blocked_modules`/
    `blocked_functions`)は、これまでGabriel(`inquisition()`)から一切
    読み込まれておらず、承認してもシステムの実際の検閲には何ら反映されない
    「学習したつもりになっているだけ」の状態だった(`angels/zadkiel_shield_decree.py`
    は承認ワークフロー自体の構造検証のみで、実際にenforceされているかは
    検証していなかった。`sefer/raziel_ledger.json`がMichael側から一切
    読まれていなかった件と同種の欠陥。本ファイル内の対になる修正も参照)。

    [安全な適用方法] `blocked_functions`(例: "loads", "load", "Unpickler")を
    裸の名前のまま`forbidden_funcs`に追加すると、`json.loads(...)`や
    `yaml.load(...)`のような全く無害な呼び出しまで"critical"判定で一律
    ブロックしてしまう重大な過剰検知になる(実機で確認: "loads"は`json`
    モジュールでも極めて一般的な関数名)。そのため、`blocked_functions`は
    `blocked_modules`との直積(例: "pickle.loads", "dill.loads")としてのみ
    `forbidden_funcs`に加え、完全修飾名(`qualified_name`)でのみ照合させる
    (裸の`func_name`では一致しない)ことで、意図した"pickle経由の
    デシリアライズ"のような呼び出しだけを狙い撃ちし、無関係な同名関数を
    誤検知しないようにする。`blocked_modules`自体は既存の`forbidden_modules`
    と同じ"high"(非ブロッキング)severityのまま追加するのみとし、既存の
    severity設計(bareなimportだけでは拒否しない)との一貫性を保つ。
    """
    try:
        mtime = _SHIELD_RULES_PATH.stat().st_mtime
    except OSError:
        return frozenset(), frozenset()
    if _dynamic_shield_rules_cache["mtime"] == mtime:
        return _dynamic_shield_rules_cache["modules"], _dynamic_shield_rules_cache["funcs"]
    try:
        with open(_SHIELD_RULES_PATH, "r", encoding="utf-8") as f:
            rules = json.load(f)
        modules = frozenset(
            m for m in rules.get("blocked_modules", []) if isinstance(m, str) and m
        )
        funcs = frozenset(
            f"{m}.{fn}"
            for m in modules
            for fn in rules.get("blocked_functions", [])
            if isinstance(fn, str) and fn
        )
    except Exception:
        modules, funcs = frozenset(), frozenset()
    _dynamic_shield_rules_cache["mtime"] = mtime
    _dynamic_shield_rules_cache["modules"] = modules
    _dynamic_shield_rules_cache["funcs"] = funcs
    return modules, funcs


def inquisition(source_code: str, context: dict = None) -> List[Finding]:
    findings: List[Finding] = []
    if not isinstance(source_code, str):
        return [Finding("GAB-001", "critical", 0, "Invalid input.")]
    try:
        tree = ast.parse(source_code)
    except Exception as e:
        return [Finding("GAB-003", "critical", 0, f"AST parse failed: {e}")]

    dynamic_modules, dynamic_funcs = _load_dynamic_shield_rules()
    forbidden_modules = {"pickle", "ctypes", "importlib", "socket", "urllib", "requests", "http", "subprocess", "os"} | dynamic_modules
    forbidden_funcs = {"__import__", "getattr", "eval", "exec", "compile", "os.system", "subprocess.Popen"} | dynamic_funcs
    dunder_chains = {"__class__", "__subclasses__", "__globals__", "__builtins__"}

    # [脆弱性修正 2026-10] forbidden_funcs には "os.system" / "subprocess.Popen"
    # のようなドット付き（モジュール修飾）のエントリが含まれているが、
    # 以前は呼び出し式から `node.func.attr` （最後の属性名のみ、例: "system"）
    # しか取り出しておらず、ドット付きエントリと一致することが原理的に
    # 不可能だった（実機検証済み: `os.system('rm -rf /')` は critical として
    # 一度も検知されず、importの"high"判定のみに留まっていた）。
    # 呼び出し式を可能な限り完全修飾名(例: "os.system")に復元し、
    # 短縮名・完全修飾名の両方で forbidden_funcs と照合するよう修正した。
    def _qualified_call_name(func_node) -> str:
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            base = _qualified_call_name(func_node.value)
            return f"{base}.{func_node.attr}" if base else func_node.attr
        return ""

    for node in ast.walk(tree):
        lineno = getattr(node, 'lineno', 0)

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            base_module = node.module if isinstance(node, ast.ImportFrom) else ""
            for alias in node.names:
                full_name = f"{base_module}.{alias.name}" if base_module else alias.name
                if any(seg in forbidden_modules for seg in full_name.split(".")):
                    findings.append(Finding("GAB-102", "high", lineno, f"Forbidden module detected: '{full_name}'"))

        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            qualified_name = _qualified_call_name(node.func)

            if func_name in forbidden_funcs or qualified_name in forbidden_funcs:
                findings.append(Finding("GAB-201", "critical", lineno, f"Forbidden function invocation: '{qualified_name or func_name}'"))

        elif isinstance(node, ast.Name):
            if node.id in forbidden_funcs:
                findings.append(Finding("GAB-201", "critical", lineno, f"Forbidden name reference: '{node.id}'"))

        elif isinstance(node, ast.Attribute):
            if node.attr in dunder_chains:
                findings.append(Finding("GAB-301", "high", lineno, f"Suspicious dunder attribute access: '{node.attr}'"))

    return findings

# =========================================================
# [脆弱性修正 2026-10] fd事前オープンによる書き込みバイパス対策
# -----------------------------------------------------------
# CPythonの sys.addaudithook には os.write / os.pwrite / os.writev
# に対応する監査イベントが存在しない（実機検証済み）。そのため、
# Sanctumコンテキストに入る「前」に書き込み用fdを確保しておけば、
# os.open の監査（上記）を完全に回避して任意パスへの書き込みが
# できてしまっていた。sys.addaudithookはPython本体のイベントが
# 発生しない呼び出しまでは監視できないため、ここでは os モジュール
# の関数自体をラップし、呼び出しごとに /proc/self/fd 経由で実体の
# パスを解決してポリシー照合する（Linux限定のベストエフォート策。
# 恒久対策としてはOSレベルのサンドボックス併用を強く推奨する）。
# =========================================================
_WHITELISTED_FDS = {0, 1, 2}  # stdin/stdout/stderr は監視対象外

def _resolve_fd_path(fd: int):
    try:
        link = os.readlink(f"/proc/self/fd/{fd}")
    except Exception:
        return None
    if link.startswith(("socket:", "pipe:", "anon_inode:")):
        return None
    return link

def _check_fd_not_socket_for_sendfile(fd: int, api_name: str):
    """[脆弱性修正 2026-10 §CN] `os.sendfile(out_fd, in_fd, ...)`は、
    `out_fd`がファイルではなく**ソケット**である場合、ファイル内容を
    ネットワーク経由でそのまま外部へ送出できる(実機で実際に、サーバー
    側で`recv()`した内容として到達することを確認済み――本物の情報
    持ち出しである)。しかしこのAPI自体がsys.addaudithookの監査イベントを
    一つも発火しないため(ファイル冒頭のコメント参照)、Gatekeeper
    (`maquina_gatekeeper.py`、イベント名の列挙に依存する設計)は構造的に
    一度もこの呼び出しを観測できず、forbidden集合への追加では一切
    対策にならない。本ファイル自身の`_check_fd_write_allowed`も、
    `_resolve_fd_path`が`"socket:"`で始まるリンクを(本来ファイル書き込み
    制限が対象とする「パス」が存在しないという正当な理由で)意図的に
    `None`として返し、その結果チェック自体をスキップしていたため、
    ソケット宛の送出は従来どおり無検査だった。これはファイル書き込み
    制限(allowed_dirs)の対象外という判断としては正しいが、副作用として
    ネットワーク送出の検査が一切行われていないことを、本関数で別途
    明示的に塞ぐ。許可された送信先ホストかどうかを`getpeername()`等で
    判定して選別的に許可する設計も検討したが、この隔離結界の脅威モデル
    (使い捨てスクリプトの実行)において、ファイル内容をソケットへ直接
    送出する正当な用途は想定されないため、保守的に無条件拒否とする。"""
    if getattr(_hook_state, 'in_hook', False):
        return
    if not _is_guard_active():
        return
    if fd in _WHITELISTED_FDS:
        return
    _hook_state.in_hook = True
    try:
        try:
            link = os.readlink(f"/proc/self/fd/{fd}")
        except Exception:
            return
        if link.startswith("socket:"):
            _trigger_violation(
                api_name, (fd, link),
                f"{api_name}でソケットfd(fd={fd})への送出が試みられました"
                f"(監査イベントの存在しないAPIによるネットワーク情報持ち出し、§CN)。"
            )
    finally:
        _hook_state.in_hook = False


def _check_fd_write_allowed(fd: int, api_name: str):
    if getattr(_hook_state, 'in_hook', False):
        return
    if not _is_guard_active():
        return
    if fd in _WHITELISTED_FDS:
        return
    _hook_state.in_hook = True
    try:
        policy = _get_current_policy()
        path = _resolve_fd_path(fd)
        if path is not None and not _is_path_allowed(path, policy["allowed_dirs"]):
            _trigger_violation(
                api_name, (fd, path),
                f"Unauthorized fd-based write access to '{path}' (fd={fd}, pre-opened handle bypass attempt)."
            )
    finally:
        _hook_state.in_hook = False

_ORIG_OS_WRITE = os.write
_ORIG_OS_WRITEV = getattr(os, "writev", None)
_ORIG_OS_PWRITE = getattr(os, "pwrite", None)
_ORIG_OS_PWRITEV = getattr(os, "pwritev", None)

def _guarded_os_write(fd, data):
    _check_fd_write_allowed(fd, "os.write")
    return _ORIG_OS_WRITE(fd, data)

def _guarded_os_writev(fd, buffers):
    _check_fd_write_allowed(fd, "os.writev")
    return _ORIG_OS_WRITEV(fd, buffers)

def _guarded_os_pwrite(fd, data, offset):
    _check_fd_write_allowed(fd, "os.pwrite")
    return _ORIG_OS_PWRITE(fd, data, offset)

def _guarded_os_pwritev(fd, buffers, offset, *a, **kw):
    _check_fd_write_allowed(fd, "os.pwritev")
    return _ORIG_OS_PWRITEV(fd, buffers, offset, *a, **kw)

# [脆弱性修正 2026-10 §CD] os.sendfile / os.copy_file_range によるfd事前
# オープンバイパス対策
# -----------------------------------------------------------
# 発見: §CBでmmapによるバイパスを塞いだ直後、「os.write系4関数以外に、
# カーネル側でfdからfdへ直接データを転送する別の経路はないか」を自問し、
# 実機で`sys.addaudithook`に生のコールバックを登録して検証したところ、
# `os.sendfile(out_fd, in_fd, offset, count)` と
# `os.copy_file_range(src, dst, count)` の両方が、**CPythonのaudit event
# を一切発生させない**ことを確認した(mmap.__new__ のように検査漏れの
# イベントが存在したのではなく、そもそも監査可能なイベント自体が存在
# しない)。この2関数はいずれもカーネルの同名syscall相当を直接呼び、
# ユーザー空間のバッファを経由しないため、os.write/pwrite/writev/pwritev
# のいずれも一度も呼ばない。実機検証済み: allowed_dirs外のファイルに
# ついて、Sanctumに入る前に確保した書き込み用fdへ、別のfdから
# `os.sendfile`または`os.copy_file_range`で直接データを転送する攻撃が、
# 例外を一切発生させずに成功し、ファイル内容が実際に書き換わることを
# 確認した。
#
# 対応: 監査イベントが存在しない以上、既存のos.write系4関数と全く同じ
# 方針で、`os`モジュールのこの2関数自体をラップし、書き込み先fd
# (out_fd / dst)を既存の`_check_fd_write_allowed`に通す。
#
# [正直に残る限界] 同じ調査の過程で、Sanctumに入る「前」に確保した
# Pythonファイルオブジェクト(`open(path, 'r+b')`等が返す
# `io.FileIO`/`io.BufferedWriter`)の`.write()`メソッドも、同様に
# 監査イベントを発生させず、本修正後もSanctumを完全に迂回して
# 書き込めることを実機で確認した。これはCPythonの`_io`拡張型の
# メソッドで、`io.FileIO.write = ...`のような通常の属性代入による
# モンキーパッチが`TypeError: cannot set 'write' attribute of
# immutable type '_io.FileIO'`で拒否されることも実機で確認しており
# (ctypesで型オブジェクトのメモリを直接書き換えるような極めて脆い
# 手段を除けば)、本ファイルが採用している「osモジュールの関数を
# Python層でラップする」という設計そのものの限界に当たる。恒久対策
# にはOSレベルのサンドボックス(seccomp等)が必要であり、この限界は
# 既にファイル冒頭のコメントで述べている通り、意図的に正直に記録して
# おく。
_ORIG_OS_SENDFILE = getattr(os, "sendfile", None)
_ORIG_OS_COPY_FILE_RANGE = getattr(os, "copy_file_range", None)

def _guarded_os_sendfile(out_fd, in_fd, offset, count, *a, **kw):
    # [§CN] ソケット宛の送出は、ファイル書き込み制限(allowed_dirs)の
    # 対象外であると同時に、ネットワーク情報持ち出しの対象でもあるため、
    # 別の専用チェックで明示的に拒否する(_check_fd_write_allowedは
    # ソケットを"パス無し"として素通りさせるだけで、これのみでは
    # 塞がれない)。
    _check_fd_not_socket_for_sendfile(out_fd, "os.sendfile")
    _check_fd_write_allowed(out_fd, "os.sendfile")
    return _ORIG_OS_SENDFILE(out_fd, in_fd, offset, count, *a, **kw)

def _guarded_os_copy_file_range(src, dst, count, offset_src=None, offset_dst=None):
    _check_fd_not_socket_for_sendfile(dst, "os.copy_file_range")
    _check_fd_write_allowed(dst, "os.copy_file_range")
    return _ORIG_OS_COPY_FILE_RANGE(src, dst, count, offset_src, offset_dst)

# [脆弱性修正 2026-10 §CO] §CNの調査直後、同じ「audit eventが存在しない
# API」という観点を、プロセス起動・通信系の他のAPIにも体系的に広げて
# 再確認したところ、`socket.socket.send()`/`sendall()`が、実機で確認した
# 限り**一度も**audit eventを発火しないことが判明した(§CA・§CM・ファイル
# 先頭のコメントが記録している`socket.connect`/`socket.sendto`/
# `socket.sendmsg`は、いずれも別個の、ちゃんと存在するeventである――
# `send`/`sendall`はそれらとは違い、そもそもイベント自体が無い)。
#
# `angels/jegudiel_exfiltration_guard.py`の§CA時点のコメントは、
# 「TCP経由のsend/sendallは専用eventを持たないが、必ず事前のconnectを
# 要する(=forbidden集合で遮断済み)ため検査不要」と判断していた。しかし
# これは、§CN・§CD等で繰り返し発見している「Sanctum起動**前**に確保した
# fd・接続は、起動後も検査を素通りする」という同じ前提openedバイパスの
# 構造を見落としていた――実機で確認したところ、Sanctum起動**前**に
# connect()しておいたソケットは、起動**後**に`.send()`/`.sendall()`で
# データを送出しても、`_michael_absolute_defense`は一度も呼ばれず
# (そもそも監査イベントが発火しないため)、無条件に成功した。これは
# §CNのsendfileより影響が大きい――sendfileより遥かに一般的に使われる
# 「ソケットへの通常のデータ送信」そのものが、無検査だったことになる。
#
# [設計方針の違い: §CNとの比較] §CNのos.sendfileは「ソケット宛の送出に
# 正当な用途が想定されない」として無条件拒否を選んだが、本件のsend/
# sendallは**ソケット通信そのものの正規の手段**であり、Sanctum起動後に
# 許可されたホスト(allowed_hosts)へ接続して送信する、という正当な
# フローを壊してはならない。そのため、既存の`_michael_absolute_defense`
# の「2. ソケット通信検査」が`connect`/`sendto`/`sendmsg`に対して行って
# いるのと同じ方針――`getpeername()`で接続先ホストを解決し、
# `allowed_hosts`ポリシーと照合する選別的な許可――を、ここでも採用する。
# これにより、起動後に許可ホストへ接続して送信する正当な利用は引き続き
# 許可され、起動**前**に許可外のホストへ接続しておいたソケットからの
# 送出だけが、正しく拒否される。
_ORIG_SOCKET_SEND = socket.socket.send
_ORIG_SOCKET_SENDALL = socket.socket.sendall


def _check_socket_send_allowed(sock, api_name: str):
    if getattr(_hook_state, 'in_hook', False):
        return
    if not _is_guard_active():
        return
    _hook_state.in_hook = True
    try:
        policy = _get_current_policy()
        try:
            peer = sock.getpeername()
        except OSError:
            # [正直な注記] 未接続(UDPソケット等)や既に切断されたソケット
            # への呼び出しは、OSError自体がこの直後に発生して処理が
            # 終わるため、ここでの拒否は不要(安全側に、呼び出し自体は
            # そのまま素通りさせて元のOSErrorに委ねる)。
            return
        target_host = peer[0] if isinstance(peer, tuple) and peer else None
        allowed_hosts = policy.get("allowed_hosts", set())
        if not target_host or target_host not in allowed_hosts:
            _trigger_violation(
                api_name, (target_host,),
                f"{api_name}でソケットの送信先'{target_host}'が許可リストに"
                f"含まれていません(Sanctum起動前の事前接続バイパス対策、§CO)。"
            )
    finally:
        _hook_state.in_hook = False


def _guarded_socket_send(self, *a, **kw):
    _check_socket_send_allowed(self, "socket.send")
    return _ORIG_SOCKET_SEND(self, *a, **kw)


def _guarded_socket_sendall(self, *a, **kw):
    _check_socket_send_allowed(self, "socket.sendall")
    return _ORIG_SOCKET_SENDALL(self, *a, **kw)


# [脆弱性修正 2026-10 §CP] 上記の`socket.socket.send`/`sendall`の修正
# (§CO)を実機で確認した直後、「TLS(HTTPS)経由の通信ではどうなるか」を
# 再確認したところ、`ssl.SSLSocket`が`send`/`sendall`を**独自に
# 上書きしている**(`socket.socket`のメソッドを呼ばない、全く別の実装)
# ことを実機で確認した。そのため、§COで`socket.socket.send`自体を
# モンキーパッチしても、`ssl.SSLSocket`のインスタンス(`ssl.wrap_socket`
# や`SSLContext.wrap_socket`が返す、`requests`・`urllib`等が内部で
# 実際に使っているTLSソケット)には一切効果が及ばない。実機で、自己
# 署名証明書を用いた本物のTLSループバック接続を確立し、Sanctum起動
# **後**に`SSLSocket.send()`で機密データを送出したところ、§COの修正後
# でも例外無しに成功し、受信側に実際にデータが届くことを確認した――
# §COより**さらに実際的な**経路である(AIが生成したコードが外部APIへ
# 通信する場合、`requests`等の通常の経路は常にTLSを経由するため)。
#
# [一般化] §CA→§CN→§CO→本件という連鎖は、「あるクラスのメソッドを
# モンキーパッチで塞いだつもりでも、そのクラスをサブクラス化し同名の
# メソッドを独自実装で上書きしているクラスには、親クラスへのパッチが
# 及ばない」という、Pythonのメソッド解決順序(MRO)に起因する、
# これまでとは異なる種類の見落としである。`socket.socket`のメソッドを
# 塞いだ際、「このメソッドをオーバーライドしている標準ライブラリの
# サブクラスは他に無いか」を確認する、という新しい観点を得た。
#
# 対応は§COの`_check_socket_send_allowed`をそのまま再利用する
# (`ssl.SSLSocket`は`socket.socket`のサブクラスであり、`getpeername()`
# は基底クラスの実装がそのまま使える)。
_ORIG_SSL_SOCKET_SEND = ssl.SSLSocket.send
_ORIG_SSL_SOCKET_SENDALL = ssl.SSLSocket.sendall


def _guarded_ssl_socket_send(self, *a, **kw):
    _check_socket_send_allowed(self, "ssl.SSLSocket.send")
    return _ORIG_SSL_SOCKET_SEND(self, *a, **kw)


def _guarded_ssl_socket_sendall(self, *a, **kw):
    _check_socket_send_allowed(self, "ssl.SSLSocket.sendall")
    return _ORIG_SSL_SOCKET_SENDALL(self, *a, **kw)


def _create_awaken():
    _awakened = False
    def awaken():
        nonlocal _awakened
        if _awakened:
            return
        sys.addaudithook(_michael_absolute_defense)
        os.write = _guarded_os_write
        if _ORIG_OS_WRITEV:
            os.writev = _guarded_os_writev
        if _ORIG_OS_PWRITE:
            os.pwrite = _guarded_os_pwrite
        if _ORIG_OS_PWRITEV:
            os.pwritev = _guarded_os_pwritev
        if _ORIG_OS_SENDFILE:
            os.sendfile = _guarded_os_sendfile
        if _ORIG_OS_COPY_FILE_RANGE:
            os.copy_file_range = _guarded_os_copy_file_range
        socket.socket.send = _guarded_socket_send
        socket.socket.sendall = _guarded_socket_sendall
        ssl.SSLSocket.send = _guarded_ssl_socket_send
        ssl.SSLSocket.sendall = _guarded_ssl_socket_sendall
        _awakened = True
    return awaken

awaken = _create_awaken()
awaken()
