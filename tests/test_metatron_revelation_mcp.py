"""
tests/test_metatron_revelation_mcp.py
=====================================
[新設 2026-11] angels/metatron_revelation_mcp.py の単体テスト。

本天使(「メタトロンの啓示」)は、Armageddonエンジン
(`tartarus/armageddon.py`・`tartarus/armageddon_core.py`)の自動ルール
更新が、必ず人間承認キュー(`raziel_ledger_pending.json`・
`PENDING_HUMAN_REVIEW`)を経由する実装になっているかを静的に検証する
(思考統制監査)。天使群のテストカバレッジの棚卸しの過程で、専用テスト
が一件も存在しないことが判明した。

`main()`は`ROOT / "tartarus" / "armageddon.py"`等の固定パスを直接読む
ため、`metatron_revelation_mcp.ROOT`を一時ディレクトリへmonkeypatchし、
各検査項目を満たす/満たさないフィクスチャを置いて検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import metatron_revelation_mcp as mrm

VALID_ARMAGEDDON_CORE_TEXT = (
    "PENDING_LEDGER_PATH = 'raziel_ledger_pending.json'\n"
    "PENDING_HUMAN_REVIEW = 'pending'\n"
    "def apply_new_seal(rule):\n"
    "    queue_for_review(rule)\n"
)


def _write_fixtures(root, core_text=VALID_ARMAGEDDON_CORE_TEXT, main_text=""):
    tartarus_dir = root / "tartarus"
    tartarus_dir.mkdir(parents=True, exist_ok=True)
    (tartarus_dir / "armageddon.py").write_text(main_text, encoding="utf-8")
    (tartarus_dir / "armageddon_core.py").write_text(core_text, encoding="utf-8")


def _expect_fail(monkeypatch, root):
    monkeypatch.setattr(mrm, "ROOT", root)
    try:
        mrm.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_real_repository_passes_or_is_not_applicable():
    """[実機の裏付け] 現時点のリポジトリでは、Armageddonエンジンが
    人間承認ゲートを経由する実装になっているか、該当ファイル自体が
    まだ存在しないため、本天使はPASSまたはNOT_APPLICABLEのいずれかを
    報告する(FAILではない)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        mrm.main()
    out = buf.getvalue()
    assert ("✅ PASS" in out) or ("⬜ NOT_APPLICABLE" in out)


def test_reports_not_applicable_when_neither_file_exists(monkeypatch, tmp_path):
    """armageddon.py・armageddon_core.pyのいずれも存在しない場合は、
    PASSではなくNOT_APPLICABLEを報告する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(mrm, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        mrm.main()
    assert "⬜ NOT_APPLICABLE" in buf.getvalue()


def test_fails_when_pending_ledger_path_is_missing(monkeypatch, tmp_path):
    """[核心・人間承認ゲート迂回の検知] PENDING_LEDGER_PATHへの言及が
    見つからない場合、正しくFAILする。"""
    bad_core = VALID_ARMAGEDDON_CORE_TEXT.replace("PENDING_LEDGER_PATH", "DIRECT_LEDGER_PATH")
    _write_fixtures(tmp_path, core_text=bad_core)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_pending_human_review_is_missing(monkeypatch, tmp_path):
    """[核心・人間承認ゲート迂回の検知] PENDING_HUMAN_REVIEWへの言及が
    見つからない場合、正しくFAILする。"""
    bad_core = VALID_ARMAGEDDON_CORE_TEXT.replace("PENDING_HUMAN_REVIEW", "AUTO_APPLIED")
    _write_fixtures(tmp_path, core_text=bad_core)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_apply_new_seal_is_missing(monkeypatch, tmp_path):
    """[核心] apply_new_seal()自体が見つからない場合、承認キュー化
    ロジックの欠落として正しくFAILする。"""
    bad_core = VALID_ARMAGEDDON_CORE_TEXT.replace("def apply_new_seal", "def legacy_apply_seal")
    _write_fixtures(tmp_path, core_text=bad_core)
    _expect_fail(monkeypatch, tmp_path)


def test_passes_when_checks_satisfied_via_armageddon_py_alone(monkeypatch, tmp_path):
    """armageddon_core.pyが存在せず、armageddon.py単体に全条件が揃って
    いる場合でも(2026-10分離前の構成)、両ファイルの内容を結合して
    判定するため正しくPASSすることを確認する。"""
    import io
    from contextlib import redirect_stdout

    tartarus_dir = tmp_path / "tartarus"
    tartarus_dir.mkdir(parents=True)
    (tartarus_dir / "armageddon.py").write_text(VALID_ARMAGEDDON_CORE_TEXT, encoding="utf-8")
    monkeypatch.setattr(mrm, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        mrm.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_with_all_valid_fixtures(monkeypatch, tmp_path):
    """全ての条件を満たす最小構成のフィクスチャでは、想定どおりPASS
    する(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    _write_fixtures(tmp_path)
    monkeypatch.setattr(mrm, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        mrm.main()
    assert "✅ PASS" in buf.getvalue()
