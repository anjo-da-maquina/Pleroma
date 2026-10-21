import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "メタトロンの立方体 (Metatron Cube HSM)"


# ハードウェア証明監査: ataraxia_certificate.json の署名ペイロードに
# 必須フィールド(hardware_fingerprint等)が揃っているかを検証する
# (実HSMは未接続のため、証明書フォーマットの健全性チェックに留める)。
REQUIRED_FIELDS = {"client_id", "hardware_fingerprint", "valid_until"}

def main():
    cert = load_json("ataraxia_certificate.json")
    if cert is None:
        report_not_applicable(NAME, "証明書が未発行のため検査対象なし。")
        return
    payload = cert.get("payload", {})
    missing = REQUIRED_FIELDS - payload.keys()
    if missing:
        report_fail(NAME, f"証明書payloadに必須フィールドが欠落しています: {missing}")
    if "signature" not in cert:
        report_fail(NAME, "証明書に signature フィールドがありません。")
    report_pass(NAME, "証明書のフォーマットと必須フィールドを確認しました。")

if __name__ == "__main__":
    main()
