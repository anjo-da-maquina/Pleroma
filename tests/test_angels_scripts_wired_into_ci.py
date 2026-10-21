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


def _is_literal_always_false(if_value) -> bool:
    """[脆弱性修正 2026-10 §BU] ステップの`if:`条件が、常に偽になる
    リテラル値(`false`・`0`・空文字列、またはそれらを`${{ }}`で囲んだ
    形)かどうかを判定する。GitHub ActionsのYAML上、`if: false`は
    Python側でブール値Falseとしてパースされる一方、`if: '${{ false }}'`
    のように書けば文字列として残るため、両方の表現に対応する。"""
    if if_value is False:
        return True
    if if_value is None:
        return False  # 条件未指定 = 既定でsuccess()相当。偽ではない。
    s = str(if_value).strip()
    if s.startswith("${{") and s.endswith("}}"):
        s = s[3:-2].strip()
    return s.lower() in {"false", "0", ""}


def _collect_referenced_angel_scripts() -> set:
    """全ワークフローファイルのrun:ステップの文字列を構造的に解析し、
    "angels/<ファイル名>.py" という形で実際に実行されているスクリプト名
    の集合を返す。

    [脆弱性修正 2026-10 §BU] 以前は、ステップの`if:`条件を一切見ずに
    `run:`文字列に"angels/<ファイル名>.py"が含まれているかだけで判定して
    いたため、ステップに`if: false`(常に偽になる条件)を追加するだけで、
    当該の天使をCI上で実質的に無効化できるにもかかわらず、本テストは
    「配線済み」と誤って判定し続けてしまう(実機で実際に再現して確認した
    自己言及的な欠陥)という欠陥があった。常に偽になる`if:`条件を持つ
    ステップは「配線されている」とみなさないよう修正する。"""
    referenced = set()
    for wf_path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        workflow = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            for step in job.get("steps", []):
                if _is_literal_always_false(step.get("if")):
                    continue
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


def test_step_disabled_via_literal_if_false_is_not_counted_as_wired(monkeypatch, tmp_path):
    """[核心・§BU・実機で再現して発見した自己言及的な欠陥] CIワークフロー
    上のある天使のステップに`if: false`を追加するだけで、本来CI上で
    実行されなくなる(=実質的に無効化される)にもかかわらず、修正前の
    `_collect_referenced_angel_scripts()`は`run:`文字列に名前が残っている
    ことだけを見て「配線済み」と誤判定し続けていた。これは監査システム
    自身(本テスト)に対する最も単純な無効化攻撃であり、実際にリポジトリの
    ワークフローファイルを複製して`if: false`を注入し、再現して確認した
    上で修正した。"""
    import test_angels_scripts_wired_into_ci as self_mod  # noqa: F401 (このモジュール自身)

    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "sabotaged.yml").write_text(
        "jobs:\n"
        "  test_job:\n"
        "    steps:\n"
        "      - name: sabotaged step\n"
        "        if: false\n"
        "        run: python angels/barachiel_last_words.py\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(self_mod, "WORKFLOWS_DIR", wf_dir)
    referenced = self_mod._collect_referenced_angel_scripts()
    assert "barachiel_last_words.py" not in referenced, (
        "if: false で無効化されたステップが、配線済みとして誤って検知されている。"
    )


def test_step_with_normal_condition_is_still_counted_as_wired(monkeypatch, tmp_path):
    """[回帰防止] `if: success()`のような通常の(常に偽ではない)条件は、
    これまでと同様に「配線済み」として正しく認識され続けることを確認する
    (§BUの修正による過剰検知防止)。"""
    import test_angels_scripts_wired_into_ci as self_mod

    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "normal.yml").write_text(
        "jobs:\n"
        "  test_job:\n"
        "    steps:\n"
        "      - name: normal step\n"
        "        if: success()\n"
        "        run: python angels/barachiel_last_words.py\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(self_mod, "WORKFLOWS_DIR", wf_dir)
    referenced = self_mod._collect_referenced_angel_scripts()
    assert "barachiel_last_words.py" in referenced
