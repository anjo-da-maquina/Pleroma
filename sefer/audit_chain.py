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

    [脆弱性修正 2026-10 §BX] 上記のクラスdocstringは「改ざん・削除を行え
    ない」と謳っていたが、実際には**鍵を一切知らなくても**、`log_path`
    自身への書き込み権限さえあれば、ファイルを空(0バイト、または空の
    JSON配列)に切り詰めるだけで監査証跡の全件を跡形もなく消去できる
    ことを実機で確認した。`verify_integrity()`は「ファイルが存在しない」
    場合に`True`を返す設計だが、「ファイルが存在するが0件」の場合も
    ループが一度も実行されずに同じく`True`を返してしまうため、この2つの
    状態が区別できなかった。HMACによる鍵付けは「既存の行を書き換える」
    攻撃は防ぐが、「全ての行を削除する」攻撃には何の防御も提供しない
    ――これは2026-10の先行修正(本ファイル冒頭のコメント参照)が意図して
    防いだはずの「侵入の証拠を跡形もなく消せてしまう」攻撃が、鍵の知識
    すら不要な、より単純な形でそのまま残っていたことを意味する。

    本修正では、鍵ファイルと同じディレクトリに「最後に記録した
    (index, hash)の水位標(watermark)」を保持する別ファイルを追加した。
    `record()`は新しいエントリを追記するたびに水位標も更新し、
    `verify_integrity()`は、ログファイルから実際に読み取れた最終エントリ
    が、この水位標が記録している(index, hash)と一致するかどうかも検証
    する。これにより、ログファイルを鍵なしで(部分的に、または全件)
    切り詰める攻撃は、水位標との不一致として検知できるようになる。
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
        # [脆弱性修正 2026-10 §BX] 水位標ファイルは鍵ファイルと同じ
        # ディレクトリ・同じ命名規則に置く(鍵ファイルと同じ保護前提を
        # 共有する設計上の判断であり、実際の保護の強さはSanctumの
        # allowed_dirs設定に依存する――本クラス単体では変更できない
        # 前提であることを正直に注記する)。
        self.watermark_path = self.key_path.parent / (self.key_path.name + ".watermark")

    def _read_watermark(self):
        try:
            with open(self.watermark_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("index", 0), data.get("hash", "0" * 64)
        except Exception:
            return 0, "0" * 64

    def _write_watermark(self, index: int, current_hash: str):
        try:
            with open(self.watermark_path, "w", encoding="utf-8") as f:
                json.dump({"index": index, "hash": current_hash}, f)
        except OSError:
            # [正直な注記] 水位標の書き込み自体に失敗しても、ログの記録
            # (record()の主たる責務)は継続させる。水位標が更新されない
            # 場合、次回のverify_integrity()はこの時点のエントリ数までの
            # 整合性は検証できなくなるが、既存のログ記録機能そのものを
            # 止めてしまうほうが実害が大きいと判断した。
            pass

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

        # [脆弱性修正 2026-10 §BX] ログファイル自体への追記成功後、
        # 鍵ファイルと同じ場所にある水位標も更新する。これにより、
        # 後から誰かがlog_pathを鍵なしで切り詰めても、verify_integrity()
        # が「本来はここまで記録されていたはずだ」と検知できる。
        self._write_watermark(new_index, entry["hash"])

    def verify_integrity(self) -> bool:
        # [脆弱性修正 2026-10 §BX] 以前は「ファイルが存在しない」場合に
        # Trueを返していたが、「ファイルが存在するが0件(切り詰め済み)」
        # の場合も、以下のループが一度も実行されずに同じくTrueを返して
        # しまい、この2つの状態を区別できなかった。水位標が「本来N件
        # 記録されていたはずだ」と記憶していれば、ここで既に不一致を
        # 検知できる(下記の最終チェックへ処理を進める)。
        watermark_index, watermark_hash = self._read_watermark()

        if not self.log_path.exists():
            return watermark_index == 0

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

        final_index = expected_index - 1
        final_hash = expected_prev_hash

        # [脆弱性修正 2026-10 §BX・核心] ログファイル自体のチェーンとしては
        # 整合していても、鍵ファイルと同じ場所にある水位標が記憶している
        # 「本来ここまで記録されていたはずだ」という事実と食い違う場合は、
        # ログファイルが鍵なしで切り詰められた(全件、または一部の末尾
        # エントリが削除された)ことを意味するため、改ざんとして検知する。
        if watermark_index > final_index:
            return False
        if watermark_index == final_index and not hmac.compare_digest(watermark_hash, final_hash):
            return False

        return True
