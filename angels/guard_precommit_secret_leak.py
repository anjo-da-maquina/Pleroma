import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "guard_precommit_secret_leak (Blademaster) - 機密情報漏洩カナリア: dummy_secrets(意図的ハニーポット)を除外し、 コミット対象に実際の秘密情報らしきパターンが紛れていないかを静的走査する。"


# 機密情報漏洩カナリア: dummy_secrets(意図的ハニーポット)を除外し、
# コミット対象に実際の秘密情報らしきパターンが紛れていないかを静的走査する。
#
# [2026-10 追記] これまでは本チェックがCI/手動実行時にしか走らず、秘密情報が
# 一度git履歴に刻まれてから初めて検知される「事後検知」のみだった。
# tools/pre_commit_secret_scan.py + hooks/pre-commit により、コミット自体を
# 事前にブロックする層を追加した。本関数は、その配線(hooks/pre-commit が
# 実際にスキャンスクリプトを呼んでいること)が将来静かに外されていないかを
# 併せて静的検証する。
def _verify_pre_commit_hook_wiring():
    hook_path = ROOT / "hooks" / "pre-commit"
    scan_script = ROOT / "tools" / "pre_commit_secret_scan.py"
    if not hook_path.exists():
        report_fail(NAME, "hooks/pre-commit が存在しません。pre-commitでのシークレットスキャンが無効化されています。")
    if not scan_script.exists():
        report_fail(NAME, "tools/pre_commit_secret_scan.py が存在しません。")
    hook_text = hook_path.read_text(encoding="utf-8-sig")
    if "pre_commit_secret_scan.py" not in hook_text:
        report_fail(NAME, "hooks/pre-commit が tools/pre_commit_secret_scan.py を呼び出していません。")


def main():
    _verify_pre_commit_hook_wiring()

    hits = scan_for_leaked_secrets()
    if hits:
        details = "\n".join(f"  - {path} (pattern={pattern})" for path, pattern in hits)
        report_fail(NAME, f"秘密情報らしきパターンを検知しました:\n{details}")
    report_pass(NAME, "リポジトリ内に秘密情報の漏洩パターンは検出されず、pre-commitフックの配線も健全です。")

if __name__ == "__main__":
    main()
