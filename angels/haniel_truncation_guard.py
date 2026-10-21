import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "ハニエルの水位標検問 (Haniel's Watermark Gate - 監査証跡の切り詰め消去検知)"

# [新設 2026-10 §BX] 実際に発見した具体例: `sefer/audit_chain.py`の
# `SignedAuditChain.verify_integrity()`、および`maquina_gatekeeper.py`の
# `ZKAuditTrail._verify_full_chain()`はいずれも、鍵付きHMAC-SHA256による
# 改ざん耐性を謳っていたが、「ログファイル自体を鍵の知識なしに空へ
# 切り詰める」という、暗号的な知識を一切必要としないもっと単純な攻撃に
# 対しては、何の防御も提供していなかった。両者とも「ファイル(または
# チェーン)が0件」の場合、無条件にTrue(=改ざん無し)を返す設計だった
# ため、「まだ何も記録されていない、本当に初回の状態」と「攻撃者が
# 過去の全記録(侵入の証拠を含む)を消去した状態」を一切区別できな
# かった。実機で、鍵ファイルを一切読まずにログファイルを空にするだけで
# 両方の`verify_integrity()`/`_verify_full_chain()`が改ざんを検知せずに
# 通過することを確認した上で、鍵ファイルと同じ場所に「最後に記録した
# (件数, 最終ハッシュ)」を記憶する水位標(watermark)ファイルを導入し、
# 両者を修正した。
#
# [一般化の方針] `angels/remiel_equivalence_battery.py`(§BW)と同じ設計
# 思想――個々の実装の書き方を解析するのではなく、実際にリポジトリに
# 存在する改ざん検知機構を直接呼び出し、既知の攻撃(ここでは「ログ全体
# を鍵なしで切り詰める」)を実際に与えて、正しく検知されることを継続的
# に検証する回帰連戦である。
#
# [正直な注記: 本検査の限界] (1) 本天使が検証するのは「ログファイルを
# 鍵なしで切り詰める」という既知の具体的な攻撃のみであり、将来新たに
# 追加される別の改ざん検知機構(現時点では未知)には自動的には及ばない。
# (2) 水位標ファイル自体も、ログファイルと同じディレクトリ・同じ
# ファイルシステム権限で保護される前提であり、攻撃者が水位標ファイルと
# ログファイルの両方を同時に削除・改ざんできる(例: ディレクトリ全体を
# 削除してから両方を再生成する)場合は、この修正の範囲外である――これは
# 本フレームワーク全体が前提とする脅威モデル(sefer.Sanctum配下に
# サンドボックス化された、allowed_dirs外のファイルには手が届かない
# 未信頼AIコード)に依存する、各クラスのdocstringが既に明記している
# 限界である。

sys.path.insert(0, str(ROOT))


def _check_signed_audit_chain() -> tuple:
    """sefer.audit_chain.SignedAuditChainを対象に、切り詰め攻撃後も
    正しく検知できるかを確認する。戻り値: (success: bool, detail: str)"""
    from sefer.audit_chain import SignedAuditChain

    tmp_dir = tempfile.mkdtemp(prefix="haniel_sac_")
    try:
        log_path = os.path.join(tmp_dir, "audit_chain.jsonl")
        key_path = os.path.join(tmp_dir, ".audit_signing_key")
        chain = SignedAuditChain(log_path=log_path, key_path=key_path)
        chain.record("legit_action_1", {})
        chain.record("INCRIMINATING_LOG", {})

        if chain.verify_integrity() is not True:
            return False, "改ざん前の正規チェーンが検証に失敗した(前提条件の異常)"

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("")

        if chain.verify_integrity() is not False:
            return False, "ログ全体を空に切り詰めても改ざんが検知されなかった"
        return True, "OK"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _check_zk_audit_trail() -> tuple:
    """maquina_gatekeeper.ZKAuditTrailを対象に、切り詰め攻撃後も正しく
    検知できるかを確認する。戻り値: (success: bool, detail: str)"""
    import maquina_gatekeeper as mg

    original_cwd = os.getcwd()
    tmp_dir = tempfile.mkdtemp(prefix="haniel_zkt_")
    try:
        os.chdir(tmp_dir)
        mg.ZKAuditTrail.verify_and_record("legit_action_1")
        mg.ZKAuditTrail.verify_and_record("INCRIMINATING_LOG")

        with open(mg.ZKAuditTrail.FILE_NAME, "w", encoding="utf-8") as f:
            json.dump([], f)

        try:
            mg.ZKAuditTrail.verify_and_record("post_truncation_action")
            return False, "ログ全体を[]に切り詰めても改ざんが検知されなかった"
        except mg.LossOfAtaraxia:
            return True, "OK"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_dir, ignore_errors=True)


CHECKS = [
    ("sefer.audit_chain.SignedAuditChain", _check_signed_audit_chain),
    ("maquina_gatekeeper.ZKAuditTrail", _check_zk_audit_trail),
]


def run_battery():
    """全ての監査証跡実装に対し、切り詰め攻撃が正しく検知されるかを
    確認する。戻り値: [(name, detail), ...] (失敗したものだけ)"""
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
            f"監査証跡の切り詰め(全件消去)攻撃が、少なくとも1つの実装で"
            f"検知されませんでした(§BXの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        f"{len(CHECKS)}個の監査証跡実装すべてに対し、鍵の知識無しでの"
        f"ログ全体の切り詰め(証拠消去)攻撃が正しく検知されることを確認しました。",
    )


if __name__ == "__main__":
    main()
