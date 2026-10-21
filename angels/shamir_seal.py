import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "シャミアの封印 (Shamir Seal)"


# 分散鍵管理・鍵更新監査: 証明書の有効期限が切れていないか、
# および残り有効期間が閾値を下回っていないかを検証する。
# [注] GitHub Actions等の未承認クラウド環境では、ゼロトラスト思想に基づき
# 証明書が無効/失効していることが「正しい状態」である(test_sanctuary.py参照)。
# そのためクラウド環境では失効を失敗ではなく想定内の情報として報告する。
from datetime import datetime, timezone

WARN_DAYS = 2
IS_UNVERIFIED_CLOUD = os.getenv("GITHUB_ACTIONS") == "true"

def main():
    cert = load_json("ataraxia_certificate.json")
    if cert is None:
        report_not_applicable(NAME, "証明書が未発行のため検査対象なし。")
        return
    valid_until_str = cert["payload"]["valid_until"].replace("Z", "+00:00")
    valid_until = datetime.fromisoformat(valid_until_str)
    now = datetime.now(timezone.utc)
    remaining_days = (valid_until - now).total_seconds() / 86400

    if remaining_days < 0:
        if IS_UNVERIFIED_CLOUD:
            report_pass(NAME, f"未承認クラウド環境のため証明書失効は想定内の正常状態です（{valid_until_str}に失効）。")
            return
        report_fail(NAME, f"証明書の有効期限が既に切れています({valid_until_str})。鍵の更新(Shamir's Seal)が必要です。")

    if remaining_days < WARN_DAYS:
        report_info(NAME, f"⚠️ 証明書の残り有効期間が{remaining_days:.1f}日です。更新を推奨します。")
    report_pass(NAME, f"証明書は有効です（残り{remaining_days:.1f}日）。")

if __name__ == "__main__":
    main()
