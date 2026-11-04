"""
tests/test_guard_shield_rule_autoapply_and_key_leak.py
=====================================
[新設 2026-11] angels/guard_shield_rule_autoapply_and_key_leak.py の単体テスト。

本天使(「ザドキエルの勅令」)は、外部脅威インテリジェンス取り込み機構
(src/angelic_shield.py・src/kamael_judgment.py)の再構築が、以下5点の
修正を保ったままであることを静的に検証する:
  A. LLM生出力をshield_rules.jsonへ直接反映せず、人間承認待ちキュー
     (shield_rules_pending.json)に積むのみであること。
  B. tools/promote_shield_seal.pyによる人間承認の昇格経路が存在する
     こと。
  C. GEMINI_API_KEYをos.environ.pop()で即時消去していること。
  D. KamaelInquisitorが完全修飾名(例: "os.system")でも照合すること。
  E. 誤解を招く独自audit hookの重複実装(metatrons_seal)が復活して
     いないこと。

report_fail()は呼び出し即座にsys.exit(1)するため、各チェックは
main()内で先頭から順に評価され、最初に満たさない条件のみが報告される。
天使群のテストカバレッジの棚卸しの過程で、専用テストが一件も存在
しないことが判明した。本天使はLLM生出力の自動反映という本質的に
危険な経路(思考統制監査)を守る中核であるため、優先して対応する。

`main()`は`ROOT / "src" / "angelic_shield.py"`等の固定パスを直接読む
ため、`guard_shield_rule_autoapply_and_key_leak.ROOT`を一時ディレクトリへmonkeypatchし、
各検査項目を満たす/満たさないフィクスチャを置いて検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import guard_shield_rule_autoapply_and_key_leak as zsd

VALID_SHIELD_TEXT = (
    "import os\n"
    "class ZadkielDominion:\n"
    "    def propose_knowledge(self, data):\n"
    "        self._queue('shield_rules_pending')\n"
    "    def _clear_key(self):\n"
    "        os.environ.pop(\"GEMINI_API_KEY\", None)\n"
)

VALID_JUDGMENT_TEXT = (
    "class KamaelInquisitor:\n"
    "    def _qualified_call_name(self, frame):\n"
    "        return 'os.system'\n"
)

VALID_PROMOTE_TEXT = (
    "PENDING_HUMAN_REVIEW = 'pending'\n"
    "def promote(status):\n"
    "    if status == PENDING_HUMAN_REVIEW:\n"
    "        pass\n"
)


def _write_fixtures(root, shield_text=VALID_SHIELD_TEXT, judgment_text=VALID_JUDGMENT_TEXT,
                     promote_text=VALID_PROMOTE_TEXT, include_shield=True, include_judgment=True,
                     include_promote=True):
    src_dir = root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tools_dir = root / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    if include_shield:
        (src_dir / "angelic_shield.py").write_text(shield_text, encoding="utf-8")
    if include_judgment:
        (src_dir / "kamael_judgment.py").write_text(judgment_text, encoding="utf-8")
    if include_promote:
        (tools_dir / "promote_shield_seal.py").write_text(promote_text, encoding="utf-8")


def _expect_fail(monkeypatch, root):
    monkeypatch.setattr(zsd, "ROOT", root)
    try:
        zsd.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、思考統制監査の5条件すべてが
    保たれているため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        zsd.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_required_file_is_missing(monkeypatch, tmp_path):
    """angelic_shield.py・kamael_judgment.py・promote_shield_seal.pyの
    いずれかが存在しない場合、正しくFAILする。"""
    _write_fixtures(tmp_path, include_promote=False)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_pending_queue_is_absent(monkeypatch, tmp_path):
    """[核心・A] 承認待ちキュー(shield_rules_pending)への言及自体が無い
    場合、正しくFAILする。"""
    bad_shield = VALID_SHIELD_TEXT.replace("shield_rules_pending", "shield_rules_direct")
    _write_fixtures(tmp_path, shield_text=bad_shield)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_direct_reflection_method_is_revived(monkeypatch, tmp_path):
    """[核心・A・退行検知] LLM出力を即時反映する旧メソッド
    'assimilate_knowledge' が復活している場合、正しくFAILする。"""
    bad_shield = VALID_SHIELD_TEXT.replace(
        "def propose_knowledge(self, data):",
        "def assimilate_knowledge(self, data):\n    def propose_knowledge(self, data):",
    )
    _write_fixtures(tmp_path, shield_text=bad_shield)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_promote_tool_lacks_pending_status(monkeypatch, tmp_path):
    """[核心・B] promote_shield_seal.pyに人間承認待ちステータス
    (PENDING_HUMAN_REVIEW)の処理が見つからない場合、正しくFAILする。"""
    bad_promote = VALID_PROMOTE_TEXT.replace("PENDING_HUMAN_REVIEW", "SOME_OTHER_STATUS")
    _write_fixtures(tmp_path, promote_text=bad_promote)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_api_key_is_not_popped(monkeypatch, tmp_path):
    """[核心・C・窃取防止の欠落検知] GEMINI_API_KEYがos.environ.pop()で
    即時消去されていない(os.environ.get()等の読み取り専用に戻っている)
    場合、正しくFAILする。"""
    bad_shield = VALID_SHIELD_TEXT.replace(
        'os.environ.pop("GEMINI_API_KEY", None)', 'os.environ.get("GEMINI_API_KEY")'
    )
    _write_fixtures(tmp_path, shield_text=bad_shield)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_qualified_call_name_check_is_missing(monkeypatch, tmp_path):
    """[核心・D] KamaelInquisitorが完全修飾関数名(_qualified_call_name)
    を照合していない場合、正しくFAILする(sefer.inquisition()と同じ
    ドット付き禁止名の検知漏れの再発防止)。"""
    bad_judgment = VALID_JUDGMENT_TEXT.replace("_qualified_call_name", "_call_name")
    _write_fixtures(tmp_path, judgment_text=bad_judgment)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_duplicate_audit_hook_is_revived_in_shield(monkeypatch, tmp_path):
    """[核心・E] 撤去済みの独自audit hook実装(metatrons_seal)が
    angelic_shield.py側に復活している場合、正しくFAILする。"""
    bad_shield = VALID_SHIELD_TEXT + "\n    def metatrons_seal(self):\n        pass\n"
    _write_fixtures(tmp_path, shield_text=bad_shield)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_duplicate_audit_hook_is_revived_in_judgment(monkeypatch, tmp_path):
    """同様に、kamael_judgment.py側にmetatrons_sealが復活している場合も
    正しくFAILする。"""
    bad_judgment = VALID_JUDGMENT_TEXT + "\n    def metatrons_seal(self):\n        pass\n"
    _write_fixtures(tmp_path, judgment_text=bad_judgment)
    _expect_fail(monkeypatch, tmp_path)


def test_passes_with_all_valid_fixtures(monkeypatch, tmp_path):
    """全ての条件を満たす最小構成のフィクスチャでは、想定どおりPASS
    する(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    _write_fixtures(tmp_path)
    monkeypatch.setattr(zsd, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        zsd.main()
    assert "✅ PASS" in buf.getvalue()
