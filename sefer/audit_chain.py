import hmac
import json
import os
import time
import hashlib
from pathlib import Path

# [脆弱性修正 2026-10] 以前の実装は、クラス名が"Signed"(署名付き)と
# 名乗っているにもかかわらず、実際には秘密鍵もいかなる署名も使わない
# 「単純なSHA-256ハッシュ連鎖」に過ぎなかった。これは「意図しない破損の
# 検知」には有効だが、「ファイルへの書き込み権限を持つ攻撃者による
# 意図的な改ざん」には何の防御にもならない。実機検証済み: 任意の行
# (侵入検知の記録等)を削除した上で、残りのチェーンを先頭から秘密鍵なしに
# 再計算して書き直すだけで、verify_integrity()は改ざんを一切検知せず
# Trueを返し続けてしまう(=侵入の証拠を跡形もなく消せてしまう)。
#
# この閾値を上げるため、各エントリのハッシュを単純なSHA-256から、
# ローカルに保管する秘密鍵(_DEFAULT_KEY_PATH、初回自動生成・0600権限)で
# 鍵付けしたHMAC-SHA256に変更した。これにより、鍵ファイルを読めない
# 攻撃者(=本フレームワークが主に想定する、sefer.Sanctum配下に閉じ込め
# られた未信頼AIコードであり、鍵ファイルのパスはallowed_dirs外にある
# ため、Michaelの絶対防壁により読み書きともに遮断される)は、チェーンを
# 整合性を保ったまま改ざん・偽装できなくなる。
#
# [残存する限界(誠実に明記する)] 本機構は「sefer.Sanctumでサンドボックス化
# された未信頼コードによる改ざん」を防ぐためのものであり、ホストOS上で
# 鍵ファイル自体を読み書きできるだけの特権(root等、サンドボックスの外側)
# を持つ攻撃者までは防げない。それは本フレームワーク全体が前提とする
# 脅威モデル(Sanctum配下のAIコードの脱走防止)の範囲外であり、外部の
# 改ざん不可能な監査サービスやHSM等、別のアーキテクチャでしか解決できない。


def _load_or_create_signing_key(key_path: Path) -> bytes:
    key_path = Path(key_path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_bytes()

    new_key = os.urandom(32)
    # 新規生成時のみ0600(所有者のみ読み書き可)で作成する。
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_key)
    except FileExistsError:
        # 競合で他プロセスが先に作成した場合は、そちらを読み直す。
        return key_path.read_bytes()
    return new_key


class SignedAuditChain:
    """
    HMAC-SHA256による鍵付きハッシュチェーンを用いた、追跡可能・改ざん検知可能な
    監査ログ。鍵ファイル(既定: sefer/.audit_signing_key)を読めない攻撃者は、
    チェーンの整合性を保ったまま既存エントリの改ざん・削除・偽装を行えない。
    """
    def __init__(self, log_path: str = "sefer/audit_chain.jsonl", key_path: str = None):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # [テスト容易性のため 2026-10] key_pathを明示しない場合、既定では
        # log_pathと同じディレクトリの".audit_signing_key"を使う(本番既定値
        # は従来通り"sefer/.audit_signing_key"のまま)。これにより、
        # tmp_path等でlog_pathだけを差し替えるテストでも、実リポジトリの
        # sefer/.audit_signing_key を意図せず読み書き・共有してしまう
        # (テスト間の汚染・本番鍵ファイルへの誤書き込み)ことを防ぐ。
        self.key_path = Path(key_path) if key_path else (self.log_path.parent / ".audit_signing_key")
        self._key = _load_or_create_signing_key(self.key_path)

    def _compute_hash(self, entry_without_hash: dict) -> str:
        raw = json.dumps(entry_without_hash, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hmac.new(self._key, raw, hashlib.sha256).hexdigest()

    def record(self, event: str, details: dict):
        last_entry = {"index": 0, "hash": "0" * 64}
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            last_entry = json.loads(line)
            except Exception:
                pass

        new_index = last_entry["index"] + 1
        prev_hash = last_entry["hash"]

        entry = {
            "index": new_index,
            "timestamp": time.time(),
            "event": event,
            "details": details,
            "prev_hash": prev_hash
        }

        # ハッシュ計算からhashキー自身を除外して直列化
        entry["hash"] = self._compute_hash(entry)

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def verify_integrity(self) -> bool:
        if not self.log_path.exists():
            return True

        expected_prev_hash = "0" * 64
        expected_index = 1

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)

                    if entry["index"] != expected_index:
                        return False
                    if entry["prev_hash"] != expected_prev_hash:
                        # ハッシュチェーンの不一致（改ざん検知）
                        return False

                    current_hash = entry["hash"]
                    check_entry = entry.copy()
                    check_entry.pop("hash", None)
                    calculated_hash = self._compute_hash(check_entry)

                    # [脆弱性修正 2026-10] 文字列の`==`比較はタイミング攻撃に
                    # 対して理論上の弱さがあるため、hmac.compare_digest()による
                    # 定数時間比較に変更した。
                    if not hmac.compare_digest(current_hash, calculated_hash):
                        return False

                    expected_prev_hash = current_hash
                    expected_index += 1
        except Exception:
            return False

        return True
