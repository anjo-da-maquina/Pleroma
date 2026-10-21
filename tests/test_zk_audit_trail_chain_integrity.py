"""
tests/test_zk_audit_trail_chain_integrity.py
==============================================
maquina_gatekeeper.py の ZKAuditTrail の回帰テスト。GRIMOIRE.md §AH 参照。

背景: ZKAuditTrail.verify_and_record() には二つの欠陥が重なっていた。
  1. "current_hash" が秘密鍵を使わない単純なSHA-256に過ぎず、ファイルへの
     書き込み権限を持つ攻撃者がチェーンを改ざん・再計算しても検知できな
     かった(sefer/audit_chain.pyのSignedAuditChainと同種のバグ。§AE参照)。
  2. 改ざん検知が、プロセス起動時に"0000...0"へ初期化されるモジュール
     グローバル変数`_LAST_KNOWN_HASH`とファイル末尾を比較するだけだった
     ため、本フレームワークの実運用(src/ollama_agent_loop.py等、プロセス
     ごとに毎回新規起動されるCLI)では、新規プロセスの最初の呼び出しで
     比較条件が常にFalseになり、改ざん検知コードが実質的に一度も作動
     しなかった(実機検証済み)。

本修正では鍵付きHMAC-SHA256を導入し、記録の都度ファイル内のチェーン全体
を先頭から再検証するようにした。これにより、どのプロセスが最初に呼び出し
ても、ファイルに残る改ざんの痕跡を確実に検知できる。

[注意] 本ファイル名はあえて`test_thread_safety_maquina_seal.py`より辞書順
で後になるよう選んである。`mini_pytest.py`は全テストファイルを同一プロセス
内で辞書順(`sorted(tests_dir.glob("test_*.py"))`)に読み込み、
`sys.modules`を共有するため、本ファイルが`maquina_gatekeeper`(内部で
`import rsa`する)を読み込む時点で、`test_thread_safety_maquina_seal.py`が
既に設置した完全互換の疑似`rsa`モジュールが`sys.modules`に存在している
必要がある(実運用の`rsa`パッケージは本サンドボックスのegressポリシー上
インストールできないため)。
"""
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import maquina_gatekeeper as mg  # noqa: E402


def _chdir_isolated(tmp_path, monkeypatch):
    """ZKAuditTrailはカレントディレクトリ基準の相対パスでファイルを読み書き
    するため、テストごとに独立した一時ディレクトリへ移動して汚染を防ぐ。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mg, "_ZK_SIGNING_KEY_PATH", Path(".zk_audit_signing_key"))


def test_fresh_chain_records_successfully(tmp_path, monkeypatch):
    """何も改ざんされていない状態では、通常通り記録でき例外も出ない。"""
    _chdir_isolated(tmp_path, monkeypatch)
    mg.ZKAuditTrail.verify_and_record("some_action", 1, 2, key="value")

    with open(mg.ZKAuditTrail.FILE_NAME, "r", encoding="utf-8") as f:
        trail = json.load(f)
    assert len(trail) == 1
    assert trail[0]["action"] == "some_action"
    assert trail[0]["previous_hash"] == mg._GENESIS_HASH


def test_chain_links_correctly_across_multiple_records(tmp_path, monkeypatch):
    """複数回記録すると、各ブロックのprevious_hashが前のブロックの
    current_hashと正しく連結し、かつ鍵付きHMACの再検証にも通る。"""
    _chdir_isolated(tmp_path, monkeypatch)
    mg.ZKAuditTrail.verify_and_record("action_1")
    mg.ZKAuditTrail.verify_and_record("action_2")
    mg.ZKAuditTrail.verify_and_record("action_3")  # 例外が出なければ成功

    with open(mg.ZKAuditTrail.FILE_NAME, "r", encoding="utf-8") as f:
        trail = json.load(f)
    assert len(trail) == 3
    assert trail[1]["previous_hash"] == trail[0]["current_hash"]
    assert trail[2]["previous_hash"] == trail[1]["current_hash"]


def test_tampered_entry_cannot_be_forged_without_the_secret_key(tmp_path, monkeypatch):
    """[脆弱性修正の核心] あるブロック(侵入記録に相当)を削除し、
    残りのチェーンを秘密鍵なしで単純なSHA-256により再計算しても、
    次の記録呼び出しで改ざんが検知されなければならない。"""
    _chdir_isolated(tmp_path, monkeypatch)
    mg.ZKAuditTrail.verify_and_record("legit_action_1")
    mg.ZKAuditTrail.verify_and_record("INCRIMINATING_INTRUSION_LOG")
    mg.ZKAuditTrail.verify_and_record("legit_action_3")

    # 攻撃者: 2番目の(侵入を記録した)ブロックを削除し、
    # 秘密鍵を知らない状態で残りのチェーンを単純なSHA-256で再計算して
    # 書き直す(攻撃者は秘密鍵ファイルを読めないため、これしかできない)。
    with open(mg.ZKAuditTrail.FILE_NAME, "r", encoding="utf-8") as f:
        trail = json.load(f)
    assert len(trail) == 3
    forged = [trail[0]]
    prev_hash = forged[0]["current_hash"]
    survivor = trail[2]
    forged_hash = hashlib.sha256(
        f"{prev_hash}|{survivor['timestamp']}|{survivor['action']}".encode("utf-8")
    ).hexdigest()
    forged.append({
        "timestamp": survivor["timestamp"],
        "action": survivor["action"],
        "previous_hash": prev_hash,
        "current_hash": forged_hash,
        "zk_proof": survivor["zk_proof"],
    })
    with open(mg.ZKAuditTrail.FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(forged, f, indent=2)

    try:
        mg.ZKAuditTrail.verify_and_record("legit_action_4")
        assert False, (
            "修正前の欠陥が再発している: 秘密鍵なしで再計算されたチェーンの"
            "改ざんが検知されなかった。"
        )
    except mg.LossOfAtaraxia:
        pass


def test_tampering_is_detected_even_in_a_brand_new_process_run(tmp_path, monkeypatch):
    """[脆弱性修正の核心2] 旧実装はプロセス起動直後(_LAST_KNOWN_HASHが
    初期値"0000...0"のまま)の最初の呼び出しでは改ざん検知が実質的に動かな
    かった。本テストはモジュールグローバル状態を一切事前操作せず、
    「新規プロセスの最初の呼び出し」を模した状態で改ざんが検知されることを
    固定する。"""
    _chdir_isolated(tmp_path, monkeypatch)

    # 正規チェーンを1件作る
    mg.ZKAuditTrail.verify_and_record("legit_action")

    # 秘密鍵を知らない攻撃者が、鍵無しの単純なSHA-256でブロックを偽造する
    with open(mg.ZKAuditTrail.FILE_NAME, "r", encoding="utf-8") as f:
        trail = json.load(f)
    tampered_action = "FORGED_TO_HIDE_INTRUSION"
    fake_hash = hashlib.sha256(
        f"{mg._GENESIS_HASH}|{trail[0]['timestamp']}|{tampered_action}".encode("utf-8")
    ).hexdigest()
    trail[0]["action"] = tampered_action
    trail[0]["current_hash"] = fake_hash
    with open(mg.ZKAuditTrail.FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(trail, f, indent=2)

    # ここでは`_LAST_TIMESTAMP`以外、プロセス内のどのグローバル状態も
    # 「改ざん無し」を記憶していない(旧実装のバグはまさにここで検知が
    # 素通りしていた)。新しいverify_full_chainはファイルだけを根拠に
    # 検証するため、ここで必ず検知されなければならない。
    try:
        mg.ZKAuditTrail.verify_and_record("next_action")
        assert False, "新規プロセス相当の最初の呼び出しで改ざんが検知されなかった。"
    except mg.LossOfAtaraxia:
        pass


def test_truncating_the_entire_trail_to_empty_is_now_detected(tmp_path, monkeypatch):
    """
    [脆弱性修正の回帰テスト・核心 §BX] `sefer/audit_chain.py`の
    SignedAuditChainで発見した同一クラスのバグが、独立実装である
    ZKAuditTrailにも存在していた: `zk_audit_trail.json`を鍵の知識すら
    不要な単純な方法(ファイル全体を`[]`に書き換える)で切り詰めるだけで、
    `_verify_full_chain([])`が無条件に`_GENESIS_HASH`を返し、
    「まだ何も記録されていない、本当に初回の状態」であるかのように
    振る舞ってしまっていた――侵入の証拠を鍵なしで完全に消去できる
    欠陥だった。水位標ファイル(`.zk_audit_signing_key.watermark`)を
    導入した修正後は、これを検知できなければならない。
    """
    _chdir_isolated(tmp_path, monkeypatch)
    mg.ZKAuditTrail.verify_and_record("legit_action_1")
    mg.ZKAuditTrail.verify_and_record("INCRIMINATING_INTRUSION_LOG")

    with open(mg.ZKAuditTrail.FILE_NAME, "w", encoding="utf-8") as f:
        json.dump([], f)

    try:
        mg.ZKAuditTrail.verify_and_record("next_action_after_erasure")
        assert False, (
            "ログ全体を[]に切り詰めるだけで改ざんが検知されずに通過してしまった。"
        )
    except mg.LossOfAtaraxia:
        pass


def test_fresh_unused_trail_with_no_watermark_still_works(tmp_path, monkeypatch):
    """[誤検知防止] 一度もverify_and_record()を呼んでいない、真に新規の
    環境では、水位標ファイルも存在しないため、引き続き正常に初回記録
    できる。"""
    _chdir_isolated(tmp_path, monkeypatch)
    mg.ZKAuditTrail.verify_and_record("first_ever_action")
    with open(mg.ZKAuditTrail.FILE_NAME, "r", encoding="utf-8") as f:
        trail = json.load(f)
    assert len(trail) == 1


def test_zk_proof_field_is_not_a_fabricated_claim(tmp_path, monkeypatch):
    """旧実装の"zk_proof"は"Verified by Anjo da máquina"という固定文字列
    (何の検証も行わない見せかけ)だった。本修正後は、実際に行っている処理
    (鍵付きHMAC-SHA256連鎖であり、真のゼロ知識証明ではないこと)を誠実に
    説明する注記になっていることを固定する。"""
    _chdir_isolated(tmp_path, monkeypatch)
    mg.ZKAuditTrail.verify_and_record("some_action")
    with open(mg.ZKAuditTrail.FILE_NAME, "r", encoding="utf-8") as f:
        trail = json.load(f)
    assert trail[0]["zk_proof"] != "Verified by Anjo da máquina"
    assert "ゼロ知識証明ではな" in trail[0]["zk_proof"]


def test_signing_key_file_is_created_with_restrictive_permissions(tmp_path, monkeypatch):
    """自動生成される秘密鍵ファイルは、所有者のみ読み書き可能(0600)で
    作成されなければならない。"""
    _chdir_isolated(tmp_path, monkeypatch)
    mg.ZKAuditTrail.verify_and_record("some_action")
    key_path = Path(".zk_audit_signing_key")
    assert key_path.exists()
    mode = key_path.stat().st_mode & 0o777
    assert mode == 0o600, f"秘密鍵ファイルの権限が0600ではありません: {oct(mode)}"
