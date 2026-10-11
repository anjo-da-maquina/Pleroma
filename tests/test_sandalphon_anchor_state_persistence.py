"""
tests/test_sandalphon_anchor_state_persistence.py
=====================================================
angels/sandalphon_anchor.py の回帰テスト。GRIMOIRE.md §AN 参照。

背景: sandalphon_anchor.py の改ざん・ロールバック検知ロジック自体は
以前から正しかったが、その前提となる「前回実行時のチェックポイント」
(sefer/.angel_state/sandalphon_anchor.json)が、CIワークフロー上で
一度も永続化されていなかった(.angel_state/は.gitignore対象であり、かつ
ワークフローにactions/cache等の永続化手段が一件も存在しなかった)。その
結果、CI上では`load_state()`が常にNoneを返し、ロールバック検知の本体
(`if checkpoint:`分岐)が一度も実行されないまま、常にPASSを報告していた。

本テストは2つの観点を固定する:
  1. ワークフローYAMLに、`.angel_state`を対象とするactions/cacheステップが
     実際に追加され、かつそれがsandalphon_anchor.pyの実行ステップよりも
     前に配置されていること(配線の回帰防止)。
  2. sandalphon_anchor.py自身の検知ロジックが、チェックポイントが実際に
     存在する状態で正しく機能すること(ロールバック・改ざんの検知、および
     正常系での新チェックポイント保存)。これは本ロジック自体が、
     CI上で一度も実行されたことがなかった(=一度もテストで直接検証
     されていなかった)ため、合わせて固定する。
"""
import contextlib
import importlib
import io
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "anjo_da_maquina_protocol.yml"

sys.path.insert(0, str(ROOT / "angels"))


def test_ci_workflow_caches_angel_state_before_sandalphon_anchor_runs():
    """[脆弱性修正の核心] ワークフローに.angel_stateを対象とするキャッシュ
    ステップが存在し、かつsandalphon_anchor.pyの実行ステップより前に
    配置されていなければならない。配置が逆だと、復元が実行後になり
    意味をなさない。"""
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    steps = workflow["jobs"]["angelic-audit"]["steps"]

    cache_step_index = None
    anchor_step_index = None
    for i, step in enumerate(steps):
        uses = step.get("uses", "")
        run = step.get("run", "")
        if uses.startswith("actions/cache@") and ".angel_state" in str(step.get("with", {}).get("path", "")):
            cache_step_index = i
        if "sandalphon_anchor.py" in run:
            anchor_step_index = i

    assert cache_step_index is not None, (
        ".angel_state を対象とする actions/cache ステップがワークフローに見つかりません。"
        "CIの使い捨てランナー上では、チェックポイントが永続化されず"
        "ロールバック検知が機能しません。"
    )
    assert anchor_step_index is not None, "sandalphon_anchor.py を実行するステップが見つかりません。"
    assert cache_step_index < anchor_step_index, (
        "actions/cache ステップが sandalphon_anchor.py の実行より後に配置されています。"
        "復元が実行後になり、チェックポイントの検証に無意味です。"
    )


def test_cache_key_uses_run_id_so_checkpoint_actually_updates_each_run():
    """[脆弱性修正の核心] actions/cacheは、保存キーが既存のキャッシュと
    完全一致した場合、ジョブ終了時の保存自体をスキップする(GitHub Actions
    の既定挙動)。固定キーのままではチェックポイントが初回以降一切更新
    されず、2回目以降のロールバック検知が常に古い状態と比較され続けて
    しまう。保存キーに github.run_id (実行ごとに一意)を含めることで、
    実行ごとに必ず保存が発生するようにしなければならない。"""
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    steps = workflow["jobs"]["angelic-audit"]["steps"]
    cache_steps = [
        s for s in steps
        if str(s.get("uses", "")).startswith("actions/cache@")
        and ".angel_state" in str(s.get("with", {}).get("path", ""))
    ]
    assert len(cache_steps) == 1
    key = cache_steps[0]["with"]["key"]
    assert "github.run_id" in key, (
        f"キャッシュの保存キー '{key}' が github.run_id を含んでいません。"
        "固定キーのままではチェックポイントが実行ごとに更新されません。"
    )
    restore_keys = cache_steps[0]["with"].get("restore-keys", "")
    assert restore_keys, "restore-keys が設定されていません。直前のチェックポイントを復元できません。"


@pytest.fixture
def anchor_env(tmp_path, monkeypatch):
    """sandalphon_anchor.py を、一時的な監査ログ・状態ディレクトリに
    向けて実行できるようにする環境を用意する。"""
    import sandalphon_anchor as mod
    import _common as common_mod

    (tmp_path / "sefer").mkdir()
    log_path = tmp_path / "sefer" / "audit_chain.jsonl"
    state_dir = tmp_path / ".angel_state"
    state_dir.mkdir()

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(common_mod, "STATE_DIR", state_dir)

    def _write_entries(entries):
        with open(log_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    return mod, log_path, _write_entries


def _run_main_capturing_stdout(mod):
    """mini_pytestシムにはcapsysフィクスチャが無いため、標準出力を自前で
    捕捉する。report_fail()はsys.exit(1)するため、ここでSystemExitを
    捕捉し、(exit_code_or_None, 標準出力の内容) を返す。"""
    buf = io.StringIO()
    exit_code = None
    with contextlib.redirect_stdout(buf):
        try:
            mod.main()
        except SystemExit as e:
            exit_code = e.code
    return exit_code, buf.getvalue()


def test_rollback_is_detected_when_checkpoint_exists_and_log_was_truncated(anchor_env):
    """[脆弱性修正の核心] 前回実行のチェックポイントが実際に存在する状態で、
    監査ログがそのチェックポイントのindex以降を削除(ロールバック)されて
    いた場合、report_fail (exit code 1) で検知されなければならない。
    これはCI上でこれまで一度も実行されていなかった検知ロジック本体の
    直接検証である。"""
    mod, log_path, write_entries = anchor_env

    entries = [
        {"index": 1, "hash": "a" * 64},
        {"index": 2, "hash": "b" * 64},
        {"index": 3, "hash": "c" * 64},
    ]
    write_entries(entries)

    from _common import save_state
    save_state("sandalphon_anchor", {"index": 3, "hash": "c" * 64})

    # ロールバック: index=3のエントリを削除(攻撃者が末尾を巻き戻した想定)
    write_entries(entries[:2])

    exit_code, output = _run_main_capturing_stdout(mod)
    assert exit_code == 1
    assert "巻き戻し" in output


def test_tamper_is_detected_when_checkpoint_exists_and_hash_was_altered(anchor_env):
    """前回チェックポイントと同じindexのエントリが残っていても、hash値が
    書き換えられていれば改ざんとして検知されなければならない。"""
    mod, log_path, write_entries = anchor_env

    entries = [
        {"index": 1, "hash": "a" * 64},
        {"index": 2, "hash": "b" * 64},
    ]
    write_entries(entries)

    from _common import save_state
    save_state("sandalphon_anchor", {"index": 2, "hash": "b" * 64})

    # 改ざん: 同じindex=2のまま、hash値だけ書き換える
    write_entries([entries[0], {"index": 2, "hash": "TAMPERED" + "0" * 56}])

    exit_code, _ = _run_main_capturing_stdout(mod)
    assert exit_code == 1


def test_no_rollback_passes_and_saves_new_checkpoint(anchor_env):
    """[回帰防止] チェックポイントが存在し、ログがそのまま(追記のみ)で
    あれば、正常にPASSし、新しい末尾エントリで次回用のチェックポイントが
    保存されること。"""
    mod, log_path, write_entries = anchor_env

    from _common import save_state, load_state

    write_entries([{"index": 1, "hash": "a" * 64}])
    save_state("sandalphon_anchor", {"index": 1, "hash": "a" * 64})

    # 追記のみ(前回チェックポイントのindex=1はそのまま残っている)
    write_entries([
        {"index": 1, "hash": "a" * 64},
        {"index": 2, "hash": "b" * 64},
    ])

    exit_code, output = _run_main_capturing_stdout(mod)
    assert exit_code is None, "正常系でreport_fail (SystemExit)が発生してしまいました。"
    assert "✅ PASS" in output

    updated = load_state("sandalphon_anchor")
    assert updated == {"index": 2, "hash": "b" * 64}


def test_first_run_with_no_prior_checkpoint_passes_without_checking(anchor_env):
    """[回帰防止] チェックポイントが存在しない初回実行(あるいは本修正前の
    CI環境の常態)では、検証はスキップされ、新しいチェックポイントの保存
    のみが行われる。"""
    mod, log_path, write_entries = anchor_env
    write_entries([{"index": 1, "hash": "a" * 64}])

    exit_code, output = _run_main_capturing_stdout(mod)
    assert exit_code is None
    assert "✅ PASS" in output
