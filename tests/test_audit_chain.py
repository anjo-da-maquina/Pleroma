"""
[テスト追加 2026-10] sefer/audit_chain.py (SignedAuditChain) の回帰テスト。
GRIMOIRE.md §AE 参照。

背景: 以前のSignedAuditChainは"Signed"(署名付き)と名乗りながら、実際には
秘密鍵を使わない単純なSHA-256ハッシュ連鎖に過ぎなかった。これはファイルへの
書き込み権限を持つ攻撃者が、任意のエントリ(侵入検知の記録等)を削除した上で
残りのチェーンを先頭から秘密鍵なしに再計算して書き直すだけで、
verify_integrity()に改ざんを検知させずに済ませられてしまう(=侵入の証拠を
跡形もなく消せる)脆弱性だった。HMAC-SHA256による鍵付きハッシュ連鎖に変更し、
鍵ファイルを持たない攻撃者による「整合性を保った改ざん」を固定する。
"""
import json
from sefer.audit_chain import SignedAuditChain

def test_audit_chain_integrity(tmp_path):
    log_path = tmp_path / "chain.jsonl"
    chain = SignedAuditChain(log_path=str(log_path))
    chain.record("TEST_EVENT_1", {"data": "hello"})
    chain.record("TEST_EVENT_2", {"data": "world"})
    assert chain.verify_integrity() is True

def test_audit_chain_tamper_detection(tmp_path):
    log_path = tmp_path / "chain.jsonl"
    chain = SignedAuditChain(log_path=str(log_path))
    chain.record("TEST_EVENT_1", {"data": "hello"})
    
    lines = log_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["details"]["data"] = "tampered"
    lines[0] = json.dumps(entry, ensure_ascii=False)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert chain.verify_integrity() is False


def test_audit_chain_requires_secret_key_file_to_pass_verification(tmp_path):
    """
    [脆弱性修正の回帰テスト] 鍵ファイルを持たない別のSignedAuditChainインスタンス
    (=鍵を読めない攻撃者を模した状況)でチェーンを検証すると、改ざんされていない
    正規のチェーンであっても、別の鍵では検証に失敗しなければならない。
    """
    log_path = tmp_path / "chain.jsonl"
    chain = SignedAuditChain(log_path=str(log_path), key_path=str(tmp_path / "key_a"))
    chain.record("TEST_EVENT_1", {"data": "hello"})

    other_chain = SignedAuditChain(log_path=str(log_path), key_path=str(tmp_path / "key_b"))
    assert other_chain.verify_integrity() is False, (
        "鍵が異なる(=正規の鍵ファイルを持たない攻撃者を模した)状態でも"
        "検証に成功してしまっている。"
    )


def test_truncating_the_entire_log_to_empty_is_now_detected(tmp_path):
    """
    [脆弱性修正の回帰テスト・核心 §BX] 修正前は、鍵の知識すら不要な
    もっと単純な攻撃――ログファイル全体を0バイトに切り詰めるだけ――で、
    verify_integrity()が無条件にTrueを返し続けてしまっていた
    (「ファイルが存在しない」場合と「ファイルが存在するが0件」の場合を
    区別できていなかったため)。これは侵入の証拠を鍵なしで完全に消去
    できてしまう、HMAC鍵付け自体よりも根本的な欠陥だった。水位標
    (watermark)ファイルを導入した修正後は、これを検知できなければ
    ならない。
    """
    log_path = tmp_path / "chain.jsonl"
    key_path = tmp_path / "secret_key"
    chain = SignedAuditChain(log_path=str(log_path), key_path=str(key_path))

    chain.record("AI_ACTION", {"action": "read", "target": "config.json"})
    chain.record("VIOLATION", {"message": "不正なアクセスを検知し遮断した"})
    assert chain.verify_integrity() is True

    # 攻撃者(鍵を一切知らない)が、ファイルを単純に空にする。
    log_path.write_text("", encoding="utf-8")

    assert chain.verify_integrity() is False, (
        "ログ全体を0バイトに切り詰めるだけで改ざんが検知されずに通過してしまった。"
    )

    # 同じログ・鍵を指す、新規プロセスを模した別インスタンスでも検知できる
    # (水位標がプロセスの生死に依存せず、鍵ファイルと同じ場所に永続化
    # されていることの確認)。
    fresh_instance = SignedAuditChain(log_path=str(log_path), key_path=str(key_path))
    assert fresh_instance.verify_integrity() is False


def test_truncating_to_fewer_entries_is_also_detected(tmp_path):
    """切り詰めが完全な空ではなく、末尾の一部のエントリだけを削除する
    (かつ残りのチェーンはそのまま、再計算もしない)場合も検知される。"""
    log_path = tmp_path / "chain.jsonl"
    key_path = tmp_path / "secret_key"
    chain = SignedAuditChain(log_path=str(log_path), key_path=str(key_path))

    chain.record("AI_ACTION_1", {"n": 1})
    chain.record("AI_ACTION_2", {"n": 2})
    chain.record("VIOLATION", {"n": 3})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    log_path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")

    assert chain.verify_integrity() is False


def test_fresh_unused_chain_with_no_watermark_still_passes(tmp_path):
    """[誤検知防止] 一度もrecord()を呼んでいない、真に新規のチェーンは、
    水位標ファイルも存在しないため、引き続きTrueを返す。"""
    log_path = tmp_path / "chain.jsonl"
    key_path = tmp_path / "secret_key"
    chain = SignedAuditChain(log_path=str(log_path), key_path=str(key_path))
    assert chain.verify_integrity() is True


def test_tampered_entry_cannot_be_forged_without_the_secret_key(tmp_path):
    """
    [脆弱性修正の回帰テスト・核心] 修正前の単純なSHA-256ハッシュ連鎖は、
    秘密鍵を一切必要とせずに「侵入検知の記録」を削除した上でチェーンを
    先頭から再計算して書き直すだけで、改ざんを一切検知されずに済ませる
    ことができた(実機で再現・確認済み)。鍵付きHMAC-SHA256への変更後は、
    正規の鍵を知らない攻撃者が同じ手口(エントリ削除+チェーンの再計算)を
    試みても、新しいハッシュが正規の鍵で検証した値と一致しないため、
    改ざんが検知されなければならない。
    """
    log_path = tmp_path / "chain.jsonl"
    key_path = tmp_path / "secret_key"
    chain = SignedAuditChain(log_path=str(log_path), key_path=str(key_path))

    chain.record("AI_ACTION", {"action": "read", "target": "config.json"})
    chain.record("VIOLATION", {"message": "不正なアクセスを検知し遮断した"})
    chain.record("AI_ACTION", {"action": "list", "target": "."})

    assert chain.verify_integrity() is True

    # 攻撃者(正規の鍵ファイルにアクセスできない前提)が、
    # "VIOLATION"行を削除し、残りのチェーンを自力で(鍵を知らないまま)
    # 整合性を保って再計算しようと試みる。
    import hashlib
    lines = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    tampered = [lines[0], lines[2]]

    rewritten = []
    prev_hash = "0" * 64
    for i, entry in enumerate(tampered, start=1):
        new_entry = {
            "index": i,
            "timestamp": entry["timestamp"],
            "event": entry["event"],
            "details": entry["details"],
            "prev_hash": prev_hash,
        }
        # 攻撃者は秘密鍵を持たないため、素のSHA-256で偽造を試みる
        # (修正前の脆弱な実装がまさにこの計算方法だった)。
        raw = json.dumps(new_entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
        new_entry["hash"] = hashlib.sha256(raw).hexdigest()
        rewritten.append(new_entry)
        prev_hash = new_entry["hash"]

    log_path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in rewritten) + "\n",
        encoding="utf-8",
    )

    assert chain.verify_integrity() is False, (
        "修正前の欠陥が再発している: 秘密鍵を知らない攻撃者が侵入検知の"
        "記録を削除し、整合性を保ったまま改ざんできてしまった。"
    )
