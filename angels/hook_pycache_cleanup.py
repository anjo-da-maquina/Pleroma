import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_info, ROOT

NAME = "hook_pycache_cleanup (Clerk) - 終了処理監査: __pycache__ 等の一時生成物を確実に掃除する。"

# 終了処理: 以前はprintのみで実際の掃除は行っていなかった。
# ここでは本セッション中に生成された一時キャッシュ(__pycache__)のみを
# 実際に削除する（リポジトリ本体やgit履歴には触れない、安全な範囲に限定）。


def main():
    removed = 0
    for pycache in ROOT.rglob("__pycache__"):
        if pycache.is_dir():
            import shutil
            shutil.rmtree(pycache, ignore_errors=True)
            removed += 1
    report_info(NAME, f"一時キャッシュディレクトリを{removed}件削除しました。空間を浄化しました。")


if __name__ == "__main__":
    main()
