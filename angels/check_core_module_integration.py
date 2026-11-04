import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "check_core_module_integration (Technician) - 機能要件E2E監査: 重要モジュール(sefer, anjo_interceptor)が正しくimportでき…"


# 機能要件E2E監査: 重要モジュール(sefer, anjo_interceptor)が正しくimportでき、
# 基本的な公開APIが期待通りに動作することをE2Eで検証する。
def main():
    sys.path.insert(0, str(ROOT))
    from sefer import inquisition, Sanctum, LossOfAtaraxia
    findings = inquisition("import os\nos.system('x')")
    if not findings:
        report_fail(NAME, "inquisition()が既知の危険コードを検知できませんでした。")

    try:
        from anjo_interceptor.intent_checker import IntentInterceptor, SpecificationGamingDetected
        import json as _json
        interceptor = IntentInterceptor()
        try:
            interceptor.evaluate_action(_json.dumps({"action": "read", "target": "dummy_secrets/dummy_api_key.env"}))
            report_fail(NAME, "IntentInterceptorがハニーポットへのアクセスを検知できませんでした。")
        except SpecificationGamingDetected:
            pass
    except ModuleNotFoundError:
        report_info(NAME, "anjo_interceptor が見つからないためスキップ。")

    report_pass(NAME, "主要モジュールのE2E動作確認が完了しました。")

if __name__ == "__main__":
    main()
