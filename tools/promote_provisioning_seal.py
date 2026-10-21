"""
Provisioning 承認プロモーションツール
========================================
[新設 2026-10] `adapters/provisioning_agent.py` がキューイングした
環境承認の提案(`sefer/provisioning_pending.json`)を、人間が内容
（client_id・hardware_fingerprint・有効期限）を確認した上で、
`maquina_gatekeeper.py`の信頼の起点(`MAQUINA_PUBLIC_KEY_PEM`)へ
反映し、`ataraxia_certificate.json`を発行するためのツール。

これにより、提案者（本スクリプトを実行できる任意のローカル環境）が
自分自身を無条件に承認済みにできてしまう自己署名の構造的欠陥を防ぐ。
`tools/promote_shield_seal.py`(Zadkiel向け)・`tools/promote_ledger_seal.py`
(Armageddon Engine向け)と同一のパターン。

使い方:
    python tools/promote_provisioning_seal.py --list
    python tools/promote_provisioning_seal.py --approve "<client_id>"
    python tools/promote_provisioning_seal.py --reject  "<client_id>"
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

PLEROMA_DIR = Path(__file__).parent.parent
GATEKEEPER_PATH = PLEROMA_DIR / "maquina_gatekeeper.py"
CERT_PATH = PLEROMA_DIR / "ataraxia_certificate.json"
PENDING_PATH = PLEROMA_DIR / "sefer" / "provisioning_pending.json"


def _pubkey_fingerprint(pubkey_pem: str) -> str:
    return hashlib.sha256(pubkey_pem.strip().encode("utf-8")).hexdigest()


def _currently_trusted_fingerprint() -> str:
    """[脆弱性修正 2026-10 §BY] 現在`maquina_gatekeeper.py`に書かれている
    `MAQUINA_PUBLIC_KEY_PEM`(=今まさに信頼されている公開鍵)の指紋を
    読み取る。提案されている公開鍵の指紋と比較することで、人間の
    審査者が「この承認は、信頼の起点を別の鍵へ丸ごと入れ替える
    (ローテーションする)操作である」ことに気づけるようにする。"""
    try:
        gatekeeper_code = GATEKEEPER_PATH.read_text(encoding="utf-8")
        m = re.search(
            r'MAQUINA_PUBLIC_KEY_PEM = """(.*?)-----END RSA PUBLIC KEY-----"""',
            gatekeeper_code,
            flags=re.DOTALL,
        )
        if not m:
            return "(現在の信頼の起点を読み取れませんでした)"
        current_pem = m.group(1) + "-----END RSA PUBLIC KEY-----"
        return _pubkey_fingerprint(current_pem)
    except OSError:
        return "(現在の信頼の起点を読み取れませんでした)"


def _load_pending():
    if not PENDING_PATH.exists():
        return []
    with open(PENDING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_pending(entries):
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def list_pending():
    """
    [脆弱性修正 2026-10 §BY] 以前の実装は、承認によって実際に適用される
    内容(`maquina_gatekeeper.py`の信頼の起点となる公開鍵そのもの、
    `entry["public_key_pem"]`)を一切表示していなかった。審査者は
    client_id・hardware_fingerprint・有効期限だけを見て承認していたが、
    これらはいずれも「この提案が本当に正当なデバイスからのものか」を
    一切保証しない(hardware_fingerprintはローカルで誰でも計算できる
    非秘密の値であり、client_idは単なる自己申告の文字列である)。
    つまり、`sefer/provisioning_pending.json`への書き込み権限を持つ
    攻撃者が、見た目上は全く正常な提案(本物のclient_id・本物の
    hardware_fingerprint)に、攻撃者自身が生成した鍵対の公開鍵・署名を
    組み合わせて偽の提案を紛れ込ませても、審査者はそれを見分ける手段を
    一切与えられていなかった(実機で、`--list`の出力に`public_key_pem`
    への言及が一切無いことを確認した)。`tools/promote_shield_seal.py`
    の`list_pending()`が、実際に適用される内容(dangerous_modules/
    dangerous_functions)をそのまま表示しているのとは非対称な状態
    だった。

    本修正では、提案されている公開鍵のSHA-256指紋を表示し、現在実際に
    信頼されている公開鍵の指紋とも比較表示する。これにより、審査者は
    「この提案は信頼の起点を別の鍵へ丸ごと入れ替える操作である」ことを
    認識でき、指紋を提案元のデバイス操作者と別経路(電話・既知の記録等)
    で照合する手がかりを得られる。
    """
    pending = _load_pending()
    open_items = [p for p in pending if p.get("status") == "PENDING_HUMAN_REVIEW"]
    if not open_items:
        print("承認待ちの提案はありません。")
        return
    current_fp = _currently_trusted_fingerprint()
    for p in open_items:
        payload = p["payload"]
        proposed_fp = _pubkey_fingerprint(p["public_key_pem"])
        print(f"--- {payload['client_id']} (requested_at={p['requested_at']}) ---")
        print(f"  hardware_fingerprint      : {payload['hardware_fingerprint']}")
        print(f"  valid_until               : {payload['valid_until']}")
        print(f"  提案された公開鍵の指紋(SHA256): {proposed_fp}")
        print(f"  現在信頼されている鍵の指紋    : {current_fp}")
        if proposed_fp == current_fp:
            print("  [情報] 現在と同一の鍵です(鍵のローテーションはありません)。")
        else:
            print(
                "  [重要] この承認は、信頼の起点(公開鍵)を別の鍵へ丸ごと"
                "入れ替えます。提案元のデバイス操作者と、この指紋を別経路"
                "(電話等)で照合してから承認してください。"
            )
        print()


def _find_pending(client_id):
    pending = _load_pending()
    matches = [p for p in pending if p["payload"]["client_id"] == client_id and p.get("status") == "PENDING_HUMAN_REVIEW"]
    return pending, matches


def approve(client_id):
    """
    [脆弱性修正 2026-10 §BK] 以前は同一client_idに複数の承認待ち提案が
    あった場合、最新のもの(`matches[-1]`)だけをAPPROVEDにし、それ以外の
    古い重複提案は"PENDING_HUMAN_REVIEW"のまま残っていた。これは
    `tools/promote_shield_seal.py`が§ATで既に修正した「同じ名前で複数回
    提案されたうちの古いエントリが、後から誤って再承認・再適用されてしまう」
    欠陥と全く同じ構造だが、本ファイルだけその対策が欠けていた非対称な
    状態だった。

    実機検証済み: client_idが同じ2件の提案(古いOLD_FP・新しいNEW_FP)を
    キューに積み、1回目の`approve(client_id)`でNEW_FPを承認した後、
    (例えば残った古い提案を片付けるつもりで)2回目の`approve(client_id)`
    を実行すると、残っていたOLD_FPの提案が`_find_pending()`に拾われて
    承認され、`maquina_gatekeeper.py`の信頼の起点(公開鍵)と
    `ataraxia_certificate.json`が、既に失効しているはずの古い提案の内容へ
    静かにロールバックされることを確認した(ゼロトラストの信頼の起点に
    対する一種のダウングレード攻撃に相当する)。

    本修正では、最新の提案を承認すると同時に、同一client_idの他の
    古い"PENDING_HUMAN_REVIEW"提案を全て"SUPERSEDED"(上位の提案に
    取って代わられた)として明示的に解消し、二度と承認待ちとして
    拾われないようにする。
    """
    pending, matches = _find_pending(client_id)
    if not matches:
        print(f"[エラー] 承認待ちの提案に '{client_id}' は見つかりませんでした。")
        return
    entry = matches[-1]  # 同一client_idが複数あれば最新のものを採用
    for stale in matches[:-1]:
        stale["status"] = "SUPERSEDED"

    # 1. maquina_gatekeeper.py の信頼の起点(公開鍵)を更新
    gatekeeper_code = GATEKEEPER_PATH.read_text(encoding="utf-8")
    new_code, n = re.subn(
        r'MAQUINA_PUBLIC_KEY_PEM = """.*?-----END RSA PUBLIC KEY-----"""',
        f'MAQUINA_PUBLIC_KEY_PEM = """{entry["public_key_pem"]}"""',
        gatekeeper_code,
        flags=re.DOTALL,
    )
    if n == 0:
        print("[エラー] maquina_gatekeeper.py内にMAQUINA_PUBLIC_KEY_PEMが見つかりませんでした。中断します。")
        return
    GATEKEEPER_PATH.write_text(new_code, encoding="utf-8")

    # 2. 証明書を発行
    cert = {"payload": entry["payload"], "signature": entry["signature"]}
    with open(CERT_PATH, "w", encoding="utf-8") as f:
        json.dump(cert, f, indent=2)

    entry["status"] = "APPROVED"
    _save_pending(pending)

    print(f"[承認] '{client_id}' を承認しました。")
    print(f"  -> {GATEKEEPER_PATH.name} の信頼の起点を更新しました(新しい鍵の指紋: {_pubkey_fingerprint(entry['public_key_pem'])})。")
    print(f"  -> {CERT_PATH.name} を発行しました。")


def reject(client_id):
    pending, matches = _find_pending(client_id)
    if not matches:
        print(f"[エラー] 承認待ちの提案に '{client_id}' は見つかりませんでした。")
        return
    for p in matches:
        p["status"] = "REJECTED"
    _save_pending(pending)
    print(f"[拒否] '{client_id}' を拒否しました（maquina_gatekeeper.py・証明書は変更されません）。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provisioning 承認プロモーションツール")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--approve", metavar="CLIENT_ID")
    group.add_argument("--reject", metavar="CLIENT_ID")
    args = parser.parse_args()

    if args.list:
        list_pending()
    elif args.approve:
        approve(args.approve)
    elif args.reject:
        reject(args.reject)
