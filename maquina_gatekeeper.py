import json
import os
import rsa
import base64
import hashlib
import platform
import subprocess
import sys
import threading
from datetime import datetime

class LossOfAtaraxia(Exception):
    pass

_GLOBAL_SANCTUARY_LOCK = threading.Lock()
_AUDIT_HOOK_REGISTERED = False
_LAST_KNOWN_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
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
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(['reg', 'query', 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'], stderr=subprocess.STDOUT).decode('utf-8')
            return out.split()[-1].strip()
    except Exception:
        pass
    return "UNKNOWN_MACHINE_ID"

def get_absolute_hardware_fingerprint():
    return hashlib.sha256(f"{get_machine_id()}-{platform.machine()}-{platform.system()}".encode('utf-8')).hexdigest()

def _register_audit_hook_once():
    global _AUDIT_HOOK_REGISTERED
    if _AUDIT_HOOK_REGISTERED: return

    def ultimate_audit_hook(event, args):
        if not is_sanctuary_sealed(): return

        forbidden = {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "socket.connect"}
        if event in forbidden or (event == "import" and args and args[0] in {"ctypes", "_ctypes", "threading"}):
            raise LossOfAtaraxia(f"[深層保護] 不純な干渉（{event}）を破棄しました。")

        # 封鎖フラグ自体の改ざんを検知
        if event == "object.__setattr__" and hasattr(args[0], "set_sanctuary_sealed"):
            raise LossOfAtaraxia("[深層保護] 認識の改ざんを検知しました。")

    try:
        sys.addaudithook(ultimate_audit_hook)
        _AUDIT_HOOK_REGISTERED = True
    except Exception:
        pass

class ZKAuditTrail:
    FILE_NAME = "zk_audit_trail.json"
    REMOTE_LEDGER_MOCK = "remote_ledger_sync.log"

    @classmethod
    def stream_to_external_ledger(cls, block_data):
        with open(cls.REMOTE_LEDGER_MOCK, 'a', encoding='utf-8') as f:
            f.write(f"[{block_data['timestamp']}] SYNCED HASH: {block_data['current_hash']} | ACTION: {block_data['action']}\n")

    @classmethod
    def verify_and_record(cls, func_name, *args, **kwargs):
        global _LAST_KNOWN_HASH, _LAST_TIMESTAMP
        current_time = datetime.utcnow()
        if current_time < _LAST_TIMESTAMP: raise LossOfAtaraxia("[時間の偽装] 過去への逆行を検知しました。")
        _LAST_TIMESTAMP = current_time

        trail = []
        if os.path.exists(cls.FILE_NAME):
            with open(cls.FILE_NAME, 'r', encoding='utf-8') as f:
                trail = json.load(f)
                if trail and trail[-1].get("current_hash") != _LAST_KNOWN_HASH and _LAST_KNOWN_HASH != "0000000000000000000000000000000000000000000000000000000000000000":
                    raise LossOfAtaraxia("[記憶の欠落] ログが改ざんされました。")
                if trail: _LAST_KNOWN_HASH = trail[-1].get("current_hash")

        timestamp_str = current_time.isoformat() + "Z"
        current_hash = hashlib.sha256(f"{_LAST_KNOWN_HASH}|{timestamp_str}|{func_name}:{str(args)}:{str(kwargs)}".encode('utf-8')).hexdigest()

        new_block = {"timestamp": timestamp_str, "action": func_name, "previous_hash": _LAST_KNOWN_HASH, "current_hash": current_hash, "zk_proof": "Verified by Anjo da máquina"}
        trail.append(new_block)

        with open(cls.FILE_NAME, 'w', encoding='utf-8') as f: json.dump(trail, f, indent=2)
        cls.stream_to_external_ledger(new_block)
        _LAST_KNOWN_HASH = current_hash

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
