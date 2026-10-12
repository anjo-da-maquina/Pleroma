"""
[脆弱性修正 2026-10 §BC] 「天使(angels/*.py)の配線漏れ」の回帰テスト。

`angels/metatron_scripture_seal.py`は、「ライセンス証明書機構(maquina_gatekeeper)
の公開配布からの分離」を静的に検証する正しいロジックを持つスクリプトとして
実在していたが、どのCIワークフローファイルのrun:ステップからも一度も呼び出
されておらず、GRIMOIRE.mdの解説文の中だけに「配線されている」と記述されて
いた。実機検証: `grep -rl metatron_scripture_seal . --include="*.py"
--include="*.yml" --include="*.md"`でGRIMOIRE.md以外に一件もヒットしないこと
を確認した。

本テストは、この特定のファイルだけでなく、`angels/`配下の全スクリプトに対して
同じ検証を行う汎用的な回帰テストである。これにより、将来誰かが新しい天使
スクリプトを追加した際に、CIへの配線を忘れても機械的に検知できる。
"""
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ANGELS_DIR = REPO_ROOT / "angels"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# _common.py は他の天使スクリプトから import される共有ヘルパーであり、
# それ自体がCIのrun:ステップとして単独実行されることは想定されていない。
_NOT_STANDALONE_STEPS = {"_common.py"}


def _collect_referenced_angel_scripts() -> set:
    """全ワークフローファイルのrun:ステップの文字列を構造的に解析し、
    "angels/<ファイル名>.py" という形で実際に実行されているスクリプト名
    の集合を返す。"""
    referenced = set()
    for wf_path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        workflow = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            for step in job.get("steps", []):
                run_cmd = str(step.get("run", ""))
                for line in run_cmd.splitlines():
                    line = line.strip()
                    if line.startswith("python angels/") or " python angels/" in line:
                        token = line.split("angels/", 1)[1].split()[0]
                        referenced.add(token)
    return referenced


def test_every_angels_script_is_referenced_by_some_ci_workflow():
    """[修正の核心] angels/*.pyの各スクリプトが、いずれかのワークフロー
    ファイルのrun:ステップから実際にpython angels/<name>.pyとして実行
    されていることを確認する(コメントや他のキーに名前が残っているだけ
    では一致しない。§AOと同じ、構造的なYAML解析による検証)。"""
    all_scripts = {
        p.name for p in ANGELS_DIR.glob("*.py")
        if p.name not in _NOT_STANDALONE_STEPS
    }
    referenced = _collect_referenced_angel_scripts()
    missing = sorted(all_scripts - referenced)
    assert missing == [], (
        f"CIワークフローのどのrun:ステップからも呼び出されていない"
        f"angels/*.pyスクリプトがあります(配線漏れの疑い): {missing}"
    )


def test_metatron_scripture_seal_is_specifically_wired_in():
    """[回帰防止・具体例] 本件で実際に見つかった欠落ファイルを名指しで
    固定する。将来この特定のファイルが再び外れた場合にも、上の汎用テスト
    だけでなくここでも検知できるようにする。"""
    referenced = _collect_referenced_angel_scripts()
    assert "metatron_scripture_seal.py" in referenced
