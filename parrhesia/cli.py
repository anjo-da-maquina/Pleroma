"""
parrhesia/cli.py
==================
`parrhesia audit <target>` のコマンドラインエントリーポイント。

[実行方法] `python -m parrhesia.cli audit <target>`
(`pyproject.toml`に`[project.scripts]`を追加して`parrhesia`コマンド自体を
PyPI配布物として公開することは、本リポジトリのパッケージ名自体が
`sefer`であり、別パッケージの配布設定を同じ`pyproject.toml`に混在させる
ことの影響範囲が未調査なため、ここでは行わない — まずは
`python -m parrhesia.cli`で動く最小限の形で提供する)。
"""
from __future__ import annotations

import argparse
import sys

from parrhesia.audit import audit_repository, render_report


def _cmd_audit(args: argparse.Namespace) -> int:
    report = audit_repository(args.target, max_commits=args.max_commits)
    print(render_report(report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parrhesia")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser(
        "audit", help="第三者リポジトリ(ローカルにクローン済み)を読み取り専用で監査する。"
    )
    audit_parser.add_argument("target", help="監査対象リポジトリのローカルパス")
    audit_parser.add_argument(
        "--max-commits", type=int, default=50, help="検査する直近コミット数(既定: 50)"
    )
    audit_parser.set_defaults(func=_cmd_audit)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
