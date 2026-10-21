import json
import os
import rsa
import base64
import hashlib
import hmac
import platform
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

class LossOfAtaraxia(Exception):
    pass

_GLOBAL_SANCTUARY_LOCK = threading.Lock()
_AUDIT_HOOK_REGISTERED = False
_GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
_LAST_TIMESTAMP = datetime.min

# [脆弱性修正 2026-10] 以前はスレッドごとに独立した封鎖ステータス
# (threading.local()) を使っていたが、これは`ultimate_audit_hook`による
# 「深層保護」を実質的に無効化できる重大なバイパス脆弱性だった。
# `enforce_maquina_seal`デコレータは`_GLOBAL_SANCTUARY_LOCK`により呼び出し
# 自体をプロセス全体で直列化しているため、複数スレッドが同時に独立した
# 封鎖状態を持つ正当な理由はそもそも存在しない。にもかかわらず封鎖フラグ
# がスレッドローカルだったため、封鎖済みのメインスレッドの中で新規スレッド
# を一つ生成するだけで、その子スレッド内では`is_sanctuary_sealed()`が
# 常に`False`(threading.local()の既定値)を返し、`ultimate_audit_hook`が
# 一切の検査をせずに即座にreturnしてしまい、`subprocess.Popen`等の
# 禁止操作が完全に素通りしてしまうことを実機検証済み(メインスレッドでは
# 正しく遮断される同じ操作が、子スレッドでは無検査で実行できてしまう
# ことを確認)。`sefer/__init__.py`のMichael側は元々`_active_stack`を
# プロセス全体で共有するグローバルなリストとして実装しており、本件は
# それとは逆に、共有すべき状態を誤ってスレッドローカル化してしまって
# いたことが原因だった(`sefer/__init__.py`参照)。封鎖フラグをプロセス
# 全体で共有するグローバル変数に戻し、スレッドを跨いでも封鎖状態が
# 維持されるよう修正した。
_sanctuary_seal_lock = threading.Lock()
_is_sanctuary_sealed_global = False

def is_sanctuary_sealed():
    return _is_sanctuary_sealed_global

def set_sanctuary_sealed(state: bool):
    global _is_sanctuary_sealed_global
    with _sanctuary_seal_lock:
        _is_sanctuary_sealed_global = state

MAQUINA_PUBLIC_KEY_PEM = """-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEA4AbFPmuW0Uz6zwuHFm8dwiHpa9Gw53SBDmpJg/ObsS5rcMy2lbn7
F2T5UxBHAzjMIYemc9+mVE8kANIbR/8eni+LV/737A731KazGP32oGXjE5s6s99P
xHwTESbL0HMPaLgjidUR5znUadh1c8P5hYqLfVQ2/3FWoFzLahGUt8D6TPQ7xziR
dF8tyK+xV0MuRun1yOKJInzHLyfWou2ZZZDJn9keriETQmJTOFdYPia91jiG47sz
jbSEGiYZJaaEzXL92GDMW4vhGMtZbm/4ur5gF8yUYDHCNDb50AKiDz7VjRcyPvNv
60aeO2fjCmFv6O6JKpEzhKWKZPyUj0lUswIDAQAB
-----END RSA PUBLIC KEY-----"""

def get_machine_id():
    """
    [脆弱性修正 2026-10 §AS] 以前の実装は`platform.system() == "Windows"`の
    場合のみマシン固有IDを取得し、Linux・macOSでは分岐自体が存在せず、
    関数が無条件に"UNKNOWN_MACHINE_ID"という**固定文字列**を返していた。

    これは`get_absolute_hardware_fingerprint()`(証明書の発行対象を1台の
    実機に縛る「ハードウェア指紋」)の入力そのものであり、`UNKNOWN_MACHINE_ID`
    が全ホスト共通の固定値である以上、Linux・macOS上では
    `-{platform.machine()}-{platform.system()}`の部分、つまり「CPUアーキ
    テクチャとOS種別が同じであれば誰でも同一の指紋になる」という、個体
    識別としては実質的に機能していない状態だった。実機検証済み: 本
    サンドボックス(Linux/x86_64)でこの関数を直接呼び出すと、ホストの
    識別情報を一切含まない定数的な指紋が算出されることを確認した。CI
    ワークフロー(`anjo_da_maquina_protocol.yml`)は`ubuntu-latest`上で
    動くため、実運用上もっとも頻繁に通る環境がまさにこの欠陥の影響を
    受けていた。`enforce_maquina_seal`が`get_absolute_hardware_fingerprint()
    != cert['payload']['hardware_fingerprint']`で行っている「この証明書は
    本当にこのマシン用に発行されたものか」という検証が、Linux/macOS上では
    事実上「同じOS・同じアーキテクチャか」という、個体識別としては
    あまりに粗い検証に縮退してしまっていた。

    本修正でLinux・macOSにも実際のマシン固有IDを追加した:
      - Linux: systemdが管理する `/etc/machine-id`(インストールごとに
        一意、再起動をまたいで不変。無ければ`/var/lib/dbus/machine-id`に
        フォールバック)。
      - macOS: `ioreg -rd1 -c IOPlatformExpertDevice` から`IOPlatformUUID`
        を抽出する(Appleプラットフォームの標準的なハードウェア識別子)。
    """
    try:
        system = platform.system()
        if system == "Windows":
            out = subprocess.check_output(['reg', 'query', 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'], stderr=subprocess.STDOUT).decode('utf-8')
            return out.split()[-1].strip()
        elif system == "Linux":
            for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
                if candidate.exists():
                    machine_id = candidate.read_text(encoding="utf-8").strip()
                    if machine_id:
                        return machine_id
        elif system == "Darwin":
            out = subprocess.check_output(
                ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'], stderr=subprocess.STDOUT
            ).decode('utf-8')
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
    except Exception:
        pass
    # [残存する限界(誠実に明記する)] 上記いずれにも該当しない、あるいは
    # 取得に失敗したプラットフォームでは、依然として固定値にフォール
    # バックする。この場合、ハードウェア指紋による個体識別は実質的に
    # 機能せず、同一OS・同一アーキテクチャの別マシンでも同じ指紋になる。
    return "UNKNOWN_MACHINE_ID"

def get_absolute_hardware_fingerprint():
    return hashlib.sha256(f"{get_machine_id()}-{platform.machine()}-{platform.system()}".encode('utf-8')).hexdigest()

def _register_audit_hook_once():
    global _AUDIT_HOOK_REGISTERED
    if _AUDIT_HOOK_REGISTERED: return

    def ultimate_audit_hook(event, args):
        if not is_sanctuary_sealed(): return

        # [脆弱性修正 2026-10 §CA] 以前は"socket.connect"のみを遮断して
        # いたが、UDPの`socket.sendto()`は接続(connect)を一切行わずに
        # データを送信できるため、"socket.connect"というaudit eventを
        # 一度も発火させない。実機検証済み: `set_sanctuary_sealed(True)`
        # (深層保護が有効な状態)でも、`socket.sendto()`によるデータ送信が
        # 例外無しで素通りすることを確認した(TCP経由の`send`/`sendall`は
        # そもそも専用のaudit eventを持たず、必ず事前の`connect`を要する
        # ためこの経路では問題にならないことも実機で確認済み――ここで
        # 新たに塞ぐべきはUDP等の「接続不要の送信」経路のみである)。
        # §BWの「等価構文によるブロックリスト回避」(import os.path)と
        # 同種の構造――禁止したい意図(外部への通信・データ送信)は同じ
        # なのに、別のAPIを使うだけで素通りしてしまうパターンである。
        forbidden = {
            "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
            "socket.connect", "socket.sendto",
        }
        if event in forbidden or (event == "import" and args and args[0] in {"ctypes", "_ctypes", "threading"}):
            raise LossOfAtaraxia(f"[深層保護] 不純な干渉（{event}）を破棄しました。")

        # 封鎖フラグ自体の改ざんを検知
        if event == "object.__setattr__" and hasattr(args[0], "set_sanctuary_sealed"):
            raise LossOfAtaraxia("[深層保護] 認識の改ざんを検知しました。")

    # [脆弱性修正 2026-10 §BS] 以前は`except Exception: pass`で、
    # sys.addaudithook()自体の失敗を無条件に握り潰していた。これは
    # 「唯一の深層保護(ultimate_audit_hook、subprocess.Popen・os.system・
    # ctypes importなどを遮断する)の設置そのものが失敗しても、呼び出し元
    # は(例外が伝播しないため)成功したものとして処理を継続し、
    # `set_sanctuary_sealed(True)`で『封鎖済み』を宣言してしまう」という、
    # フェイルオープン(安全装置の設置失敗を、安全装置が有効であるかの
    # ように握り潰して通過させる)の典型例であり、本リポジトリのゼロ
    # トラスト思想(例: shamir_seal.pyの証明書失効時の扱い)に反する。
    # ゼロトラストの原則に従い、設置の失敗は握り潰さずそのまま伝播させ
    # (フェイルクローズ)、`enforce_maquina_seal`/`_seal_sanctuary`の
    # 呼び出し自体を失敗させることで、「保護されていないのに保護されて
    # いるかのように動作する」状態を構造的に防ぐ。
    sys.addaudithook(ultimate_audit_hook)
    _AUDIT_HOOK_REGISTERED = True

def _load_or_create_zk_signing_key(key_path: Path) -> bytes:
    """[脆弱性修正 2026-10] ZKAuditTrailのハッシュ連鎖に鍵付けするための
    ローカル専用秘密鍵。初回自動生成・0600権限で作成する
    (sefer/audit_chain.pyのSignedAuditChainと同一パターン。GRIMOIRE §AE参照)。"""
    key_path = Path(key_path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_bytes()
    new_key = os.urandom(32)
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_key)
    except FileExistsError:
        return key_path.read_bytes()
    return new_key


_ZK_SIGNING_KEY_PATH = Path(".zk_audit_signing_key")


def _zk_watermark_path() -> Path:
    """[脆弱性修正 2026-10 §BX・自己訂正] 当初、水位標のパスを
    `_ZK_WATERMARK_PATH = Path(".zk_audit_signing_key.watermark")`という
    別個のモジュールレベル定数として固定していた。しかし
    `tests/test_junit_xml_exporter_chain_verification.py`等、既存のテストは
    `monkeypatch.setattr(mg, "_ZK_SIGNING_KEY_PATH", <tmp_pathの鍵ファイル>)`
    によって鍵ファイルの場所だけを一時ディレクトリへ差し替えていたが、
    水位標の定数は追従せず、実際のリポジトリの作業ディレクトリに水位標
    ファイルを書いてしまい、テスト間で水位標の件数が汚染されて
    「水位標の方が多くの記録を記憶している」という偽の改ざん検知を
    起こしてしまった(実機のpytest実行で自ら発見・再現し、ここで訂正
    する。正直な告白: マージ前にリポジトリ全体のテストを実行したことで
    発見できた自己訂正であり、言い訳はしない)。常に現在の
    `_ZK_SIGNING_KEY_PATH`から動的に導出することで、鍵ファイルの場所を
    差し替えるテスト(やデプロイ構成)に水位標も必ず追従するよう修正した。"""
    return _ZK_SIGNING_KEY_PATH.parent / (_ZK_SIGNING_KEY_PATH.name + ".watermark")


def _read_zk_watermark() -> tuple:
    try:
        with open(_zk_watermark_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("count", 0), data.get("hash", _GENESIS_HASH)
    except Exception:
        return 0, _GENESIS_HASH


def _write_zk_watermark(count: int, current_hash: str) -> None:
    try:
        with open(_zk_watermark_path(), "w", encoding="utf-8") as f:
            json.dump({"count": count, "hash": current_hash}, f)
    except OSError:
        # [正直な注記] 水位標の書き込み自体が失敗しても、監査ログの記録
        # (verify_and_record()の主たる責務)は継続させる。
        pass


class ZKAuditTrail:
    """
    [脆弱性修正 2026-10 §AH] 以前の実装には、致命的な欠陥が二つ重なっていた。

    欠陥1(鍵無し・改ざん耐性ゼロ): "current_hash"は秘密鍵を使わない単純な
    SHA-256であり、ファイルへの書き込み権限を持つ攻撃者なら、任意のブロック
    (侵入記録等)を削除した上でチェーン全体を先頭から秘密鍵なしに再計算し
    直すだけで、検知を一切受けずに改ざんできた(sefer/audit_chain.pyの
    SignedAuditChainと同種のバグ。GRIMOIRE §AE参照)。

    欠陥2(検証自体が実質的に死んでいた): 旧実装の改ざん検知は、プロセス
    起動時に"0000...0"へ初期化される**モジュールグローバル変数**
    `_LAST_KNOWN_HASH`と、ファイル末尾の"current_hash"を比較するだけ
    だった。しかし本フレームワークの実運用では`enforce_maquina_seal`で
    保護された関数は`src/ollama_agent_loop.py`/`src/openai_agent_loop.py`
    のように**プロセスごとに毎回新規起動**されるCLIとして呼ばれる。
    つまりプロセスが起動した時点で`_LAST_KNOWN_HASH`は必ず"0000...0"に
    リセットされ、比較条件`_LAST_KNOWN_HASH != "0000...0"`が常にFalseに
    なるため、**ファイル内容がどれだけ改ざんされていても、起動直後の
    最初の記録呼び出しでは改ざん検知コードが実質的に一度も実行されない**
    (実機検証済み: チェーン全体を書き換えた状態で新規プロセスを起動しても
    例外は一切発生しない)。さらに旧実装の"zk_proof"フィールドは
    `"Verified by Anjo da máquina"`という固定文字列に過ぎず、いかなる
    証明の生成・検証ロジックも存在しない、名前だけの「ゼロ知識証明」だった。

    本修正では、プロセスの生死に依存しない恒久的な検証に変更した:
    記録の都度、ファイルに保存されている全チェーンを先頭から鍵付きHMAC-
    SHA256で再検証する(verify_full_chain)。これにより、どのプロセスが
    最初に呼び出しても、ファイル自体に残る改ざんの痕跡を確実に検知できる。
    ハッシュの入力はファイルに永続化されているフィールド
    (previous_hash, timestamp, action)のみに限定した — 旧実装はargs/kwargsも
    ハッシュ入力に含めていたが、それらはブロックに保存されないため、
    そもそも後から再計算して検証することが構造的に不可能であり、ハッシュに
    混ぜても何の改ざん耐性にも寄与していなかった(検証不能なものを
    ハッシュに混ぜるのは、検証できる体裁を整えるだけの見せかけでしかない)。
    "zk_proof"フィールドは誤解を招く固定文字列から、実際に計算している
    ものを誠実に説明する注記に変更した(本機構は真のゼロ知識証明ではない)。
    """
    FILE_NAME = "zk_audit_trail.json"
    REMOTE_LEDGER_MOCK = "remote_ledger_sync.log"

    @classmethod
    def stream_to_external_ledger(cls, block_data):
        with open(cls.REMOTE_LEDGER_MOCK, 'a', encoding='utf-8') as f:
            f.write(f"[{block_data['timestamp']}] SYNCED HASH: {block_data['current_hash']} | ACTION: {block_data['action']}\n")

    @classmethod
    def _get_key(cls) -> bytes:
        return _load_or_create_zk_signing_key(_ZK_SIGNING_KEY_PATH)

    @classmethod
    def _compute_hmac(cls, key: bytes, previous_hash: str, timestamp_str: str, action: str) -> str:
        raw = f"{previous_hash}|{timestamp_str}|{action}".encode('utf-8')
        return hmac.new(key, raw, hashlib.sha256).hexdigest()

    @classmethod
    def _verify_full_chain(cls, trail: list, key: bytes) -> str:
        """ファイルに保存されたチェーン全体を先頭から鍵付きHMACで再検証し、
        末尾のcurrent_hashを返す。プロセスの再起動を跨いだ改ざんも検知する。

        [脆弱性修正 2026-10 §BX] `trail`が空リストの場合、このループは
        一度も実行されず無条件に`_GENESIS_HASH`を返していた。これは
        「監査ログがまだ一度も書かれていない、本当に初回の状態」と
        「攻撃者が`zk_audit_trail.json`を鍵なしで`[]`に書き換え、過去の
        全記録(侵入の証拠を含む)を消去した状態」を一切区別できない
        ――`sefer/audit_chain.py`のSignedAuditChainで発見・修正した同一
        クラスのバグが、独立した実装である本クラスにも存在していた。
        `.zk_audit_signing_key`と同じ場所にある水位標
        (`_zk_watermark_path()`、鍵ファイルの場所から動的に導出する)が
        記憶している「本来ここまで記録されていたはずだ」という件数・
        最終ハッシュとの不一致も検知する。"""
        expected_prev = _GENESIS_HASH
        for block in trail:
            if block.get("previous_hash") != expected_prev:
                raise LossOfAtaraxia("[記憶の欠落] ログが改ざんされました(チェーンの連続性が不正です)。")
            recomputed = cls._compute_hmac(
                key, block.get("previous_hash", ""), block.get("timestamp", ""), block.get("action", "")
            )
            if not hmac.compare_digest(recomputed, block.get("current_hash", "")):
                raise LossOfAtaraxia("[記憶の欠落] ログが改ざんされました(鍵付きハッシュの不一致を検知)。")
            expected_prev = block["current_hash"]

        watermark_count, watermark_hash = _read_zk_watermark()
        actual_count = len(trail)
        if watermark_count > actual_count:
            raise LossOfAtaraxia(
                "[記憶の欠落] ログが改ざんされました(水位標はより多くの記録を記憶しているのに、"
                "現在のファイルには存在しません。切り詰めによる証拠消去の疑いがあります)。"
            )
        if watermark_count == actual_count and watermark_count > 0 and not hmac.compare_digest(watermark_hash, expected_prev):
            raise LossOfAtaraxia("[記憶の欠落] ログが改ざんされました(水位標の最終ハッシュと一致しません)。")

        return expected_prev

    @classmethod
    def verify_and_record(cls, func_name, *args, **kwargs):
        global _LAST_TIMESTAMP
        current_time = datetime.utcnow()
        if current_time < _LAST_TIMESTAMP: raise LossOfAtaraxia("[時間の偽装] 過去への逆行を検知しました。")
        _LAST_TIMESTAMP = current_time

        key = cls._get_key()

        trail = []
        if os.path.exists(cls.FILE_NAME):
            with open(cls.FILE_NAME, 'r', encoding='utf-8') as f:
                trail = json.load(f)

        # [脆弱性修正 2026-10] プロセスごとのグローバル変数ではなく、
        # ファイル内のチェーン全体を毎回先頭から検証する。
        last_known_hash = cls._verify_full_chain(trail, key)

        timestamp_str = current_time.isoformat() + "Z"
        current_hash = cls._compute_hmac(key, last_known_hash, timestamp_str, func_name)

        new_block = {
            "timestamp": timestamp_str,
            "action": func_name,
            "previous_hash": last_known_hash,
            "current_hash": current_hash,
            "zk_proof": (
                "これは真のゼロ知識証明ではなく、ローカル秘密鍵(.zk_audit_signing_key)で"
                "鍵付けしたHMAC-SHA256ハッシュ連鎖です(GRIMOIRE §AH参照)。"
            ),
        }
        trail.append(new_block)

        with open(cls.FILE_NAME, 'w', encoding='utf-8') as f: json.dump(trail, f, indent=2)
        # [脆弱性修正 2026-10 §BX] 追記成功後、鍵ファイルと同じ場所にある
        # 水位標も更新する。これにより、後から誰かが`zk_audit_trail.json`
        # を鍵なしで切り詰めても、次回の_verify_full_chain()が検知できる。
        _write_zk_watermark(len(trail), current_hash)
        cls.stream_to_external_ledger(new_block)

def enforce_maquina_seal(github_id, cert_path='ataraxia_certificate.json'):
    def decorator(func):
        def absolute_closure(*args, **kwargs):
            with _GLOBAL_SANCTUARY_LOCK:
                _register_audit_hook_once()
                if not os.path.exists(cert_path): raise LossOfAtaraxia("証明書が見つかりません。")
                with open(cert_path, 'r', encoding='utf-8') as f: cert = json.load(f)
                valid_until = datetime.fromisoformat(cert['payload']['valid_until'].replace('Z', '+00:00')).replace(tzinfo=None)
                if datetime.utcnow() > valid_until: raise LossOfAtaraxia("寿命が尽きました。")
                pubkey = rsa.PublicKey.load_pkcs1(MAQUINA_PUBLIC_KEY_PEM.encode('utf-8'))
                rsa.verify(json.dumps(cert['payload'], sort_keys=True).encode('utf-8'), base64.b64decode(cert['signature']), pubkey)
                if get_absolute_hardware_fingerprint() != cert['payload']['hardware_fingerprint']: raise LossOfAtaraxia("環境の指紋が一致しません。")

                set_sanctuary_sealed(True)
                try:
                    result = func(*args, **kwargs)
                finally:
                    set_sanctuary_sealed(False)

                ZKAuditTrail.verify_and_record(func.__name__, *args, **kwargs)
                return result
        return absolute_closure
    return decorator

def _seal_sanctuary():
    _register_audit_hook_once()
    set_sanctuary_sealed(True)

def _unseal_sanctuary():
    set_sanctuary_sealed(False)
