"""
tests/test_shield_rebuild.py
==============================
src/angelic_shield.py / src/kamael_judgment.py の再構築(2026-10)を検証する
回帰テスト。詳細な経緯は両モジュールのdocstring、および
angels/zadkiel_shield_decree.py 参照。

確認する点:
  1. ZadkielDominion.propose_knowledge() が、LLM生出力を即時に
     shield_rules.json へ反映せず、承認待ちキュー(pending file)に
     積むだけであること(人間承認を経ない自動ルール変更の防止)。
  2. tools/promote_shield_seal.py が、承認待ちの提案を正しく
     shield_rules.json へ昇格させること。
  3. KamaelInquisitor が完全修飾名(例: "os.system")で登録された
     禁止関数ルールを正しく検知すること(Gabrielと同種のバグ修正)。
  4. 完全修飾名とバレ名の両方が一致する場合でも、二重報告しないこと。
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))

from angelic_shield import ZadkielDominion
import kamael_judgment as kj


def test_propose_knowledge_does_not_mutate_rules_file(tmp_path):
    rules_file = tmp_path / "shield_rules.json"
    pending_file = tmp_path / "shield_rules_pending.json"
    z = ZadkielDominion(rules_file=rules_file, pending_file=pending_file)

    intel = {
        "vulnerability_name": "Fake Vuln",
        "description": "desc",
        "dangerous_modules": ["ctypes"],
        "dangerous_functions": ["os.system"],
    }
    z.propose_knowledge(intel)

    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    assert rules == {"blocked_modules": [], "blocked_functions": []}, (
        "propose_knowledge が shield_rules.json を直接変更してしまっている"
        "(人間承認を経ないルール反映は禁止)"
    )

    pending = json.loads(pending_file.read_text(encoding="utf-8"))
    assert len(pending) == 1
    assert pending[0]["status"] == "PENDING_HUMAN_REVIEW"
    assert pending[0]["vulnerability_name"] == "Fake Vuln"


def test_promote_shield_seal_approval_flow(tmp_path, monkeypatch):
    rules_file = tmp_path / "shield_rules.json"
    pending_file = tmp_path / "shield_rules_pending.json"

    import promote_shield_seal as pss
    monkeypatch.setattr(pss, "RULES_PATH", rules_file)
    monkeypatch.setattr(pss, "PENDING_RULES_PATH", pending_file)

    z = ZadkielDominion(rules_file=rules_file, pending_file=pending_file)
    z.propose_knowledge({
        "vulnerability_name": "Fake Vuln 2",
        "dangerous_modules": ["ctypes"],
        "dangerous_functions": ["os.system", "danger_call"],
    })

    pss.approve("Fake Vuln 2")

    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    assert set(rules["blocked_modules"]) == {"ctypes"}
    assert set(rules["blocked_functions"]) == {"os.system", "danger_call"}

    pending = json.loads(pending_file.read_text(encoding="utf-8"))
    assert pending[0]["status"] == "APPROVED"


def test_promote_shield_seal_approves_latest_proposal_not_stale_one(tmp_path, monkeypatch):
    """[脆弱性修正の核心] GRIMOIRE.md §AT参照。同じvulnerability_nameで
    2回目の提案を承認した場合、1回目の(既に承認済みの)古い提案のデータ
    ではなく、まさに今回承認した2回目の提案のデータがshield_rules.json
    に適用されなければならない。以前の実装は`next()`で最初に見つかった
    APPROVEDエントリ(=古い方)を誤って再適用していた。"""
    rules_file = tmp_path / "shield_rules.json"
    pending_file = tmp_path / "shield_rules_pending.json"

    import promote_shield_seal as pss
    monkeypatch.setattr(pss, "RULES_PATH", rules_file)
    monkeypatch.setattr(pss, "PENDING_RULES_PATH", pending_file)

    z = ZadkielDominion(rules_file=rules_file, pending_file=pending_file)

    # 1回目の提案・承認: "old_danger" のみを禁止
    z.propose_knowledge({
        "vulnerability_name": "Recurring Vuln",
        "dangerous_modules": ["old_mod"],
        "dangerous_functions": ["old_danger"],
    })
    pss.approve("Recurring Vuln")

    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    assert set(rules["blocked_functions"]) == {"old_danger"}

    # 2回目の提案(同じvulnerability_name、別の内容)・承認:
    # "new_danger" が新たに禁止されるべき(old_dangerはそのまま残っていてもよい)
    z.propose_knowledge({
        "vulnerability_name": "Recurring Vuln",
        "dangerous_modules": ["new_mod"],
        "dangerous_functions": ["new_danger"],
    })
    pss.approve("Recurring Vuln")

    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    assert "new_danger" in rules["blocked_functions"], (
        "2回目に承認したはずの'new_danger'がshield_rules.jsonに反映されていない"
        "(古い1回目の提案が誤って再適用されている疑い)"
    )
    assert "new_mod" in rules["blocked_modules"]


def test_kamael_inquisitor_catches_qualified_call_name():
    rules = {"blocked_modules": [], "blocked_functions": ["os.system"]}
    tree_src = "import os\nos.system('echo hacked')\n"
    import ast
    tree = ast.parse(tree_src)
    inquisitor = kj.KamaelInquisitor(rules)
    inquisitor.visit(tree)
    assert any("os.system" in v for v in inquisitor.violations), (
        "完全修飾名 'os.system' がblocked_functionsに登録されていても検知されない"
        "(Gabrielで修正済みの同種バグが再発している)"
    )
    assert len(inquisitor.violations) == 1, "同一呼び出しが重複して報告されている"


def test_kamael_inquisitor_bare_name_still_works_no_regression():
    rules = {"blocked_modules": [], "blocked_functions": ["eval"]}
    import ast
    tree = ast.parse("eval('1+1')\n")
    inquisitor = kj.KamaelInquisitor(rules)
    inquisitor.visit(tree)
    assert any("eval" in v for v in inquisitor.violations)
    assert len(inquisitor.violations) == 1


def test_execute_judgment_returns_false_on_violation_not_just_a_print(tmp_path, monkeypatch):
    """[脆弱性修正の核心] GRIMOIRE.md §AR参照。execute_judgment()は違反検知時に
    「実行不可能・破棄する」という強いメッセージを表示するだけで、以前は
    戻り値も終了コードも常に正常(True相当)だった。呼び出し元が終了コードで
    合否判定しようとしても、違反があっても後続処理が実行されてしまう構造的な
    欠陥だったため、これを固定する。"""
    rules_file = tmp_path / "shield_rules.json"
    rules_file.write_text(json.dumps({"blocked_modules": [], "blocked_functions": ["os.system"]}), encoding="utf-8")
    target_file = tmp_path / "malicious.py"
    target_file.write_text("import os\nos.system('echo hacked')\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = kj.execute_judgment(str(target_file))
    assert result is False, "防壁ルール違反があるにもかかわらず、潔白(True)と判定されている"


def test_execute_judgment_returns_true_on_clean_file(tmp_path, monkeypatch):
    """[回帰防止] 違反の無いファイルは引き続きTrue(潔白)と判定されること。"""
    rules_file = tmp_path / "shield_rules.json"
    rules_file.write_text(json.dumps({"blocked_modules": [], "blocked_functions": ["os.system"]}), encoding="utf-8")
    target_file = tmp_path / "clean.py"
    target_file.write_text("x = 1 + 1\nprint(x)\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = kj.execute_judgment(str(target_file))
    assert result is True


def test_kamael_judgment_cli_exits_nonzero_on_violation(tmp_path):
    """[脆弱性修正の核心] CLIとして実行した場合、違反検知時には終了コードが
    非ゼロになること。以前は常に終了コード0(正常終了)だったため、
    `python src/kamael_judgment.py x.py && <後続処理>` のように連鎖させる
    呼び出し元は、違反があっても後続処理を実行してしまっていた。"""
    import subprocess

    rules_file = tmp_path / "shield_rules.json"
    rules_file.write_text(json.dumps({"blocked_modules": [], "blocked_functions": ["os.system"]}), encoding="utf-8")
    target_file = tmp_path / "malicious.py"
    target_file.write_text("import os\nos.system('echo hacked')\n", encoding="utf-8")

    kamael_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "kamael_judgment.py"))
    proc = subprocess.run(
        [sys.executable, kamael_path, str(target_file)],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert proc.returncode != 0, (
        f"違反があるにもかかわらず終了コードが0でした (stdout={proc.stdout!r})"
    )


def test_kamael_judgment_cli_exits_zero_on_clean_file(tmp_path):
    """[回帰防止] 違反の無いファイルでは終了コード0(正常終了)のままであること。"""
    import subprocess

    rules_file = tmp_path / "shield_rules.json"
    rules_file.write_text(json.dumps({"blocked_modules": [], "blocked_functions": ["os.system"]}), encoding="utf-8")
    target_file = tmp_path / "clean.py"
    target_file.write_text("x = 1 + 1\nprint(x)\n", encoding="utf-8")

    kamael_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "kamael_judgment.py"))
    proc = subprocess.run(
        [sys.executable, kamael_path, str(target_file)],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"違反の無いファイルで終了コードが0になりませんでした (stdout={proc.stdout!r})"
