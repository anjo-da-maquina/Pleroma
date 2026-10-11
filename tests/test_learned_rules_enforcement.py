"""
tests/test_learned_rules_enforcement.py
==========================================
sefer/__init__.py の回帰テスト。GRIMOIRE.md §AG 参照。

背景: 本フレームワークには2つの「学習」ワークフローがあった:
  1. tartarus/armageddon.py(Lucifer vs Sefer自己対戦)が発見した新たな
     脱走経路を、人間が tools/promote_ledger_seal.py で承認し
     sefer/raziel_ledger.json に反映する。
  2. angelic_shield.py(外部LLM脅威インテリジェンス)が提案した危険な
     モジュール/関数を、人間が tools/promote_shield_seal.py で承認し
     shield_rules.json に反映する。

どちらも、承認してもMichael(_michael_absolute_defense)やGabriel
(inquisition())から一切読み込まれておらず、システムの実際の防御には
何も反映されない「学習したつもりになっているだけ」の状態だった。
本テストはその統合が正しく機能し、かつ既存の挙動を壊していないことを
固定する。

[注意] sefer は sys.addaudithook / os.write のプロセス全体への monkey
patch を行う副作用の強いモジュールであり、importlib.reload()すると
os.writeの多重ラップによる無限再帰(実機で確認済み)等、意図しない
破壊的な副作用を引き起こす。そのため本テストではモジュールの再読み込みを
一切行わず、sefer._RAZIEL_LEDGER_PATH / sefer._SHIELD_RULES_PATH と、
対応するmtimeキャッシュ辞書をmonkeypatchで直接差し替えることで、
ファイルパスだけを安全に切り替える。
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import sefer  # noqa: E402


def _point_raziel_ledger_at(monkeypatch, path: Path):
    monkeypatch.setattr(sefer, "_RAZIEL_LEDGER_PATH", path)
    monkeypatch.setattr(sefer, "_dynamic_banned_events_cache", {"mtime": None, "events": frozenset()})


def _point_shield_rules_at(monkeypatch, path: Path):
    monkeypatch.setattr(sefer, "_SHIELD_RULES_PATH", path)
    monkeypatch.setattr(
        sefer, "_dynamic_shield_rules_cache",
        {"mtime": None, "modules": frozenset(), "funcs": frozenset()},
    )


def test_raziel_ledger_unknown_approved_event_is_blocked(tmp_path, monkeypatch):
    """[脆弱性修正の回帰テスト] raziel_ledger.jsonで承認された、既存の
    どの固定カテゴリにも該当しない未知のイベントは、絶対拒否されなければ
    ならない。"""
    ledger_path = tmp_path / "raziel_ledger.json"
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump({"banned_events": ["zzz.custom_exfil_event"]}, f)
    _point_raziel_ledger_at(monkeypatch, ledger_path)

    base = tmp_path / "jail_workspace"
    base.mkdir()
    with sefer.Sanctum(allowed_dirs=[str(base)]):
        try:
            sys.audit("zzz.custom_exfil_event", "payload")
            assert False, "承認済みの未知の禁止イベントが遮断されなかった"
        except sefer.LossOfAtaraxia:
            pass


def test_raziel_ledger_unapproved_unknown_event_is_not_blocked(tmp_path, monkeypatch):
    """ledgerに登録されていない未知のイベントは、従来通り素通りする
    (新しい統合によって無関係なイベントまで誤って遮断されないことの確認)。"""
    ledger_path = tmp_path / "raziel_ledger.json"
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump({"banned_events": ["zzz.custom_exfil_event"]}, f)
    _point_raziel_ledger_at(monkeypatch, ledger_path)

    base = tmp_path / "jail_workspace"
    base.mkdir()
    with sefer.Sanctum(allowed_dirs=[str(base)]):
        sys.audit("zzz.not_in_ledger", "payload")  # 例外が出なければ成功


def test_raziel_ledger_entries_already_covered_by_existing_categories_do_not_regress(tmp_path, monkeypatch):
    """[回帰防止の核心] raziel_ledger.jsonの既定値には"os.remove"のような、
    Michaelが既に条件付きチェック(allowed_dirs)で扱っているイベント名が
    含まれる。これを本関数の先頭で無条件の絶対拒否にしてしまうと、
    AI自身のjail_workspace配下での正当なファイル操作まで一律遮断する
    重大な機能破壊になる。許可された領域内であれば従来通り許可される
    ことを固定する。"""
    ledger_path = tmp_path / "raziel_ledger.json"
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump({"banned_events": ["os.remove", "os.rename", "socket.connect"]}, f)
    _point_raziel_ledger_at(monkeypatch, ledger_path)

    base = tmp_path / "jail_workspace"
    base.mkdir()
    target = base / "ok_to_remove.txt"
    target.write_text("x", encoding="utf-8")

    with sefer.Sanctum(allowed_dirs=[str(base)]):
        os.remove(str(target))  # 例外が出なければ成功(regression無し)


def test_shield_rules_qualified_function_is_blocked_as_critical(tmp_path, monkeypatch):
    """[脆弱性修正の回帰テスト] shield_rules.jsonで承認された
    blocked_modules × blocked_functions の組み合わせ(例: "dill.loads")は、
    Gabrielのinquisition()でcritical判定されなければならない。"""
    rules_path = tmp_path / "shield_rules.json"
    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump({"blocked_modules": ["dill"], "blocked_functions": ["loads", "load"]}, f)
    _point_shield_rules_at(monkeypatch, rules_path)

    findings = sefer.inquisition("import dill\ndill.loads(b'evil')")
    critical = [f for f in findings if f.severity == "critical"]
    assert any("dill.loads" in f.message for f in critical), (
        f"動的に承認されたルールが critical として検知されなかった: {findings}"
    )


def test_shield_rules_unrelated_same_named_function_is_not_flagged(tmp_path, monkeypatch):
    """[脆弱性修正の回帰テスト・核心] blocked_functionsの裸の名前(例: "loads")を
    そのままforbidden_funcsに追加すると、json.loads(...)のような全く無害な
    呼び出しまで一律critical判定されてしまう過剰検知になる。完全修飾名
    ("dill.loads")でのみ照合し、無関係な同名関数(json.loads)は誤検知されない
    ことを固定する。"""
    rules_path = tmp_path / "shield_rules.json"
    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump({"blocked_modules": ["dill"], "blocked_functions": ["loads", "load"]}, f)
    _point_shield_rules_at(monkeypatch, rules_path)

    findings = sefer.inquisition("import json\nx = json.loads('{}')")
    assert findings == [], (
        f"修正前の欠陥が再発している: 無関係なjson.loads(...)まで誤検知された: {findings}"
    )


def test_shield_rules_missing_file_does_not_break_inquisition(tmp_path, monkeypatch):
    """shield_rules.jsonが存在しない場合でも、既存の静的解析結果に影響を
    与えてはならない(フェイルセーフ・既存挙動の維持)。"""
    _point_shield_rules_at(monkeypatch, tmp_path / "does_not_exist.json")
    findings = sefer.inquisition("eval('1+1')")
    assert any(f.rule_id == "GAB-201" for f in findings)
