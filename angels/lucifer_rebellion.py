import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "ルシファーの叛逆 (Lucifer Rebellion)"


# カオスエンジニアリング: 難読化攻撃の小規模バッテリーをSeferに対して実行し、
# 突破数をレポートする。
#
# [脆弱性修正 2026-10 §BM] 以前の実装は、1件でも突破があった場合の失敗判定を
# `CHAOS_MODE`環境変数(ワークフローの`workflow_dispatch`入力`chaos_mode`、
# 既定値false)に依存させていた。しかし`push`イベント(mainへのマージを
# 実際にゲートしている唯一のトリガー)には`github.event.inputs`自体が
# 存在しないため、通常の全てのpushで`CHAOS_MODE`は常に`false`になる。
# つまり、人間がGitHub ActionsのUI/APIから明示的に`chaos_mode`チェック
# ボックスを立てて手動再実行しない限り、`os.system`・`shell=True`・`eval`
# という最も基本的な3件のサンドボックス脱出攻撃が全て成功していても、
# 本検査は情報ログを出すだけでCIを一度も失敗させない構造になっていた。
#
# この3件の攻撃は決定論的(同じコードは常に同じ結果になる、ランダムな
# ファジングではない)であり、これらのいずれかが突破される状態を日常の
# マージで許容する正当な理由は無い。そのため、`CHAOS_MODE`による失敗
# 判定のゲートを廃止し、1件でも突破があれば常に(通常のpushでも)
# 失敗させるようにした。`CHAOS_MODE`自体は今後の拡張用の情報ログとして
# 引き続き記録するが、失敗/成功の判定には使用しない。
def main():
    chaos_mode = os.getenv("CHAOS_MODE", "false").lower() == "true"
    attacks = [
        "getattr(__import__('os'), 'system')('echo hacked')",
        "__import__('subprocess').Popen('echo hacked', shell=True)",
        "eval(\"__import__('os').system('echo hacked')\")",
    ]
    bypasses = []
    for code in attacks:
        blocked, _ = run_code_against_sefer(code)
        if not blocked:
            bypasses.append(code)
    report_info(NAME, f"{len(attacks)}件中{len(bypasses)}件が防壁を突破しました。CHAOS_MODE={chaos_mode}")
    if bypasses:
        report_fail(NAME, f"防壁突破を検知しました(通常のpushでも常に失敗します): {bypasses}")
    report_pass(NAME, "カオスエンジニアリング・バッテリーを完了しました。")

if __name__ == "__main__":
    main()
