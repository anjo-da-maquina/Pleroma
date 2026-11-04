import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "guard_obfuscated_payload_bypass - ペイロード防御監査: 難読化された攻撃パターンがGabriel(静的)かMichael(動的) のいずれかで必ず捕捉されることを検証する…"


# ペイロード防御監査: 難読化された攻撃パターンがGabriel(静的)かMichael(動的)
# のいずれかで必ず捕捉されることを検証する（両方素通りした場合のみ失敗）。
OBFUSCATED_ATTACKS = [
    "getattr(__import__('os'), 'system')('echo hacked')",
    "eval(\"__import__('os').system('echo hacked')\")",
    "x = 'o' + 's'; eval(x + '.system(\\'echo hacked\\')')",
]

def main():
    bypasses = []
    for code in OBFUSCATED_ATTACKS:
        caught_statically = inquisition_catches(code)
        blocked_dynamically, _ = run_code_against_sefer(code)
        if not caught_statically and not blocked_dynamically:
            bypasses.append(code)
    if bypasses:
        report_fail(NAME, f"{len(bypasses)}件の難読化攻撃が静的/動的検査の両方を突破しました: {bypasses}")
    report_pass(NAME, f"{len(OBFUSCATED_ATTACKS)}件の難読化攻撃を静的または動的検査で捕捉しました。")

if __name__ == "__main__":
    main()
