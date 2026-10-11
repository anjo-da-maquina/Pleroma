"""
tools/incident_reset.py
========================
[新規 2026-10] `src/uriel_phoenix.UrielPhoenix`(旧: __main__専用デモ)を
実運用の人間操作用インシデント対応ツールとして公開する。

これは「致命的な侵入が確定した後の焦土作戦（破壊と再生）」であり、通常の
タスク完了時に自動実行されるものではない。隔離領域(既定: jail_workspace)
の内容をすべて削除し、クリーンな状態で再構築する不可逆な操作であるため、
人間が侵害を確認した上で明示的に実行することを前提とする
(tools/promote_ledger_seal.py / tools/promote_shield_seal.py と同じ位置づけ)。

使い方:
    python tools/incident_reset.py                       # jail_workspace を対象に実行(確認プロンプトあり)
    python tools/incident_reset.py --core-dir my_workspace
    python tools/incident_reset.py --yes                 # 確認プロンプトをスキップ(CI/スクリプト用)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from uriel_phoenix import UrielPhoenix, UrielPhoenixUnsafeTargetError


def main():
    parser = argparse.ArgumentParser(description="侵害確定後の隔離領域リセット(焦土作戦)")
    parser.add_argument("--core-dir", default="jail_workspace", help="リセット対象の隔離領域(既定: jail_workspace)")
    parser.add_argument("--talisman", default=None, help="任意: リセット時に再生成するマーカーファイル")
    parser.add_argument("--yes", action="store_true", help="確認プロンプトをスキップする(CI/スクリプト用)")
    parser.add_argument(
        "--allow-shallow-path", action="store_true",
        help="[脆弱性修正2026-10で追加] 対象パスがルートからごく浅い(2階層未満)場合の"
        "安全装置を解除する。システム標準ディレクトリを本当に意図した特殊用途以外では使わないこと。",
    )
    args = parser.parse_args()

    # [脆弱性修正 2026-10] 確認プロンプトには、操作者が実際に何を指定したか
    # (--core-dir "."等の相対パス)ではなく、実際に削除される絶対パスを
    # 解決して表示する。操作者が意図せぬ場所を対象にしていることに、
    # 削除前に気付けるようにするため。
    resolved_core_dir = Path(args.core_dir).resolve()
    resolved_talisman = Path(args.talisman).resolve() if args.talisman else None

    if not args.yes:
        print(f"[確認] 隔離領域 '{resolved_core_dir}' の内容を完全に削除し、空の状態で再構築します。")
        if resolved_talisman is not None:
            print(f"[確認] 護符 '{resolved_talisman}' も削除・再生成します。")
        print("この操作は不可逆です。侵害調査(フォレンジック)が完了していることを確認してください。")
        answer = input("続行しますか？ [y/N]: ").strip().lower()
        if answer != "y":
            print("中止しました。")
            sys.exit(1)

    try:
        result = UrielPhoenix(
            core_dir=args.core_dir, talisman=args.talisman, allow_shallow_path=args.allow_shallow_path
        ).scorched_earth_and_rebirth()
    except UrielPhoenixUnsafeTargetError as e:
        print(f"\n{e}")
        sys.exit(1)
    print(f"\n完了: {result}")


if __name__ == "__main__":
    main()
