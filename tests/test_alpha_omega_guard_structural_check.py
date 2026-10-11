"""
tests/test_alpha_omega_guard_structural_check.py
====================================================
angels/alpha_omega_guard.py の回帰テスト。GRIMOIRE.md §AO 参照。

背景: 旧実装はCIワークフローYAMLの生のテキスト全体に対して必須ファイル名の
文字列検索を行うだけで、必須ステップの`run:`そのものが削除されていても、
ファイル名がコメント等として一回でも残っていれば検知できなかった。本検査の
存在目的は「必須ステップの削除を検知すること」そのものであるため、この
バイパスは致命的だった。

本テストは、(1) 実行コマンドが実在しないのにコメント文に名前が残っている
だけの偽ワークフローは FAIL として検知されること、(2) 正常な実ワークフロー
(実際のanjo_da_maquina_protocol.yml)は PASS すること、(3) 実際に必須ステップ
の run: を削除した場合は FAIL することを固定する。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "angels"))


@pytest.fixture
def guard_env(tmp_path, monkeypatch):
    import alpha_omega_guard as mod
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    def _write_workflow(yaml_text: str):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        (wf_dir / "anjo_da_maquina_protocol.yml").write_text(yaml_text, encoding="utf-8")

    return mod, _write_workflow


def test_comment_only_mention_is_not_enough_run_step_must_actually_exist(guard_env):
    """[脆弱性修正の核心] 必須ステップのrun:が存在せず、ファイル名が
    コメント文としてのみ残っている偽装ワークフローはFAILしなければ
    ならない。旧実装はこのケースを素通りさせていた(実機検証済み)。"""
    mod, write_workflow = guard_env
    write_workflow("""
jobs:
  angelic-audit:
    steps:
      - name: dummy step
        # 以前はここで michael_sword.py / gabriel_canary.py / raziel_auditor.py を実行していた
        run: echo hello
""")
    with pytest.raises(SystemExit) as exc_info:
        mod.main()
    assert exc_info.value.code == 1


def test_real_workflow_file_passes():
    """[回帰防止] 実リポジトリのワークフローファイルは、必須3ステップの
    run:が実在するため正常にPASSすること。"""
    import alpha_omega_guard as mod
    # 実際のROOTのまま(monkeypatchせず)実行する
    import io
    import contextlib
    buf = io.StringIO()
    exit_code = None
    with contextlib.redirect_stdout(buf):
        try:
            mod.main()
        except SystemExit as e:
            exit_code = e.code
    assert exit_code is None, f"実ワークフローでFAILしました: {buf.getvalue()}"
    assert "✅ PASS" in buf.getvalue()


def test_actual_removal_of_required_run_step_is_detected(guard_env):
    """[回帰防止] 必須ステップのうち1つ(raziel_auditor.py)のrun:行が
    実際に削除された場合、FAILとして検知されること。"""
    mod, write_workflow = guard_env
    write_workflow("""
jobs:
  angelic-audit:
    steps:
      - name: michael
        run: python angels/michael_sword.py
      - name: gabriel
        run: python angels/gabriel_canary.py
""")
    with pytest.raises(SystemExit) as exc_info:
        mod.main()
    assert exc_info.value.code == 1


def test_all_three_required_steps_present_passes(guard_env):
    """[回帰防止] 必須3ステップのrun:がすべて実在すればPASSすること。"""
    mod, write_workflow = guard_env
    write_workflow("""
jobs:
  angelic-audit:
    steps:
      - name: michael
        run: python angels/michael_sword.py
      - name: gabriel
        run: python angels/gabriel_canary.py
      - name: raziel
        run: python angels/raziel_auditor.py
""")
    import io
    import contextlib
    buf = io.StringIO()
    exit_code = None
    with contextlib.redirect_stdout(buf):
        try:
            mod.main()
        except SystemExit as e:
            exit_code = e.code
    assert exit_code is None
    assert "✅ PASS" in buf.getvalue()
