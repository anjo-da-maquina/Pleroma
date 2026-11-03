"""
tests/test_raguel_template.py
=====================================
[新設 2026-11] angels/raguel_template.py の単体テスト。

本天使(「ラグエルの鑑定」)は、OpenAI拡張用テンプレート
(`src/openai_agent_loop.py`)が、「拡張用の雛形」と称しながら防壁を
一つも統合しない張りぼてに戻されていないかを静的に検証する(思考統制
監査)。具体的には、(A)存在しない死んだフォールバックimportが実行
コードとして復活していないか、(B)sefer.Sanctum/aegis_system.AegisSystem
が実際に統合され使用されているか、(C)enforce_maquina_seal(証明書
ゲート)が維持されているか、を検証する。天使群のテストカバレッジの
棚卸しの過程で、専用テストが一件も存在しないことが判明した。

report_fail()は呼び出し即座にsys.exit(1)するため、各テストはmain()内
で評価される最初の条件のみを単独で破るフィクスチャを用いる。

`main()`は`ROOT / "src" / "openai_agent_loop.py"`という固定パスを直接
読むため、`raguel_template.ROOT`を一時ディレクトリへmonkeypatchし、各
検査項目を満たす/満たさないフィクスチャを置いて検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import raguel_template as rt

VALID_TEMPLATE_TEXT = (
    '"""\n'
    "過去の欠陥: anjo_interceptor.maquina_gatekeeper への存在しない\n"
    "フォールバックimportが死んだコードパスだった(説明のみ、実コードではない)。\n"
    '"""\n'
    "from sefer import Sanctum\n"
    "from aegis_system import AegisSystem\n"
    "\n"
    "class OpenAIAgentLoop:\n"
    "    def __init__(self):\n"
    "        self.aegis = AegisSystem()\n"
    "\n"
    "    def enforce_maquina_seal(self):\n"
    "        pass\n"
    "\n"
    "    def _execute_safe_action(self, path, data):\n"
    "        with Sanctum(path):\n"
    "            pass\n"
    "\n"
    "    def run_task(self, code):\n"
    "        self.aegis.execute_ai_intent(code)\n"
)


def _write_fixture(root, text=VALID_TEMPLATE_TEXT):
    src_dir = root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "openai_agent_loop.py").write_text(text, encoding="utf-8")


def _expect_fail(monkeypatch, root):
    monkeypatch.setattr(rt, "ROOT", root)
    try:
        rt.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、OpenAI拡張テンプレートが
    死んだフォールバックimportを持たず、Sanctum/AegisSystemによる実
    防壁統合を保っているため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rt.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_target_file_is_missing(monkeypatch, tmp_path):
    """src/openai_agent_loop.py自体が存在しない場合、正しくFAILする。"""
    _expect_fail(monkeypatch, tmp_path)


def test_docstring_mention_of_dead_import_does_not_trigger_fail(monkeypatch, tmp_path):
    """過去の欠陥をdocstringとして説明するだけの言及(実際のimport文
    ではない)は、誤検知としてFAILしないことを確認する。"""
    import io
    from contextlib import redirect_stdout

    _write_fixture(tmp_path)
    monkeypatch.setattr(rt, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rt.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_dead_fallback_import_is_revived_as_from_import(monkeypatch, tmp_path):
    """[核心・A] 存在しない死んだフォールバックimportが'from ... import'
    形式で実行コードとして復活している場合、正しくFAILする。"""
    bad_text = VALID_TEMPLATE_TEXT.replace(
        "from sefer import Sanctum",
        "from anjo_interceptor.maquina_gatekeeper import something\nfrom sefer import Sanctum",
    )
    _write_fixture(tmp_path, text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_dead_fallback_import_is_revived_as_import(monkeypatch, tmp_path):
    """[核心・A] 'import ...'形式で復活している場合も、同様に正しく
    FAILする。"""
    bad_text = VALID_TEMPLATE_TEXT.replace(
        "from sefer import Sanctum",
        "import anjo_interceptor.maquina_gatekeeper\nfrom sefer import Sanctum",
    )
    _write_fixture(tmp_path, text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_sanctum_is_not_imported(monkeypatch, tmp_path):
    """[核心・B] sefer.Sanctumがimportされていない場合、正しくFAIL
    する。"""
    bad_text = VALID_TEMPLATE_TEXT.replace("from sefer import Sanctum", "")
    _write_fixture(tmp_path, text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_aegis_system_is_not_imported(monkeypatch, tmp_path):
    """[核心・B] aegis_system.AegisSystemがimportされていない場合、
    正しくFAILする。"""
    bad_text = VALID_TEMPLATE_TEXT.replace("from aegis_system import AegisSystem", "")
    _write_fixture(tmp_path, text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_sanctum_context_is_not_actually_used(monkeypatch, tmp_path):
    """[核心・B] importはあっても、_execute_safe_actionがSanctumコンテキ
    スト内で実際にファイルI/Oを行っていない場合、正しくFAILする。"""
    bad_text = VALID_TEMPLATE_TEXT.replace("with Sanctum(path):", "if True:")
    _write_fixture(tmp_path, text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_execute_ai_intent_is_not_called(monkeypatch, tmp_path):
    """[核心・B] run_taskがAegisSystem.execute_ai_intentによる事前検閲
    を経由していない場合、正しくFAILする。"""
    bad_text = VALID_TEMPLATE_TEXT.replace("self.aegis.execute_ai_intent(code)", "pass")
    _write_fixture(tmp_path, text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_enforce_maquina_seal_is_removed(monkeypatch, tmp_path):
    """[核心・C] enforce_maquina_seal(証明書ゲート)が外れている場合、
    正しくFAILする。"""
    bad_text = VALID_TEMPLATE_TEXT.replace("enforce_maquina_seal", "legacy_seal_check")
    _write_fixture(tmp_path, text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_passes_with_all_valid_fixtures(monkeypatch, tmp_path):
    """全ての条件を満たす最小構成のフィクスチャでは、想定どおりPASS
    する(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    _write_fixture(tmp_path)
    monkeypatch.setattr(rt, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rt.main()
    assert "✅ PASS" in buf.getvalue()
