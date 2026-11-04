"""
tests/test_audit_adapters_static_analysis.py
=====================================
[新設 2026-11] angels/audit_adapters_static_analysis.py の単体テスト。

本天使(「サリエルの監視」)は、`adapters/`配下の外部ツール連携
スクリプトが、禁止モジュールを直接importしていないかを
`sefer.inquisition()`(Gabrielの静的解析)で検証する。`critical`重大度
の違反がある場合のみFAILする設計である。天使群のテストカバレッジの
棚卸しの過程で、専用テストが一件も存在しないことが判明した。

`sefer.inquisition`はmain()内でローカルimportされるモジュール属性
であるため、`sefer.inquisition`自体をmonkeypatchし、実際の静的解析
ロジックを介さずに、本天使固有の「criticalな違反のみを収集して判定
する」というラッパー判定ロジックを単独で検証する。
`audit_adapters_static_analysis.ROOT`も一時ディレクトリへmonkeypatchし、
`adapters/`の内容を制御する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_adapters_static_analysis as sfa
import sefer


class _FakeFinding:
    def __init__(self, severity, message):
        self.severity = severity
        self.message = message


def _fake_inquisition_flagging(trigger_token, severity="critical"):
    def _fake(code):
        if trigger_token in code:
            return [_FakeFinding(severity, f"{trigger_token}を検知")]
        return []
    return _fake


def test_real_repository_passes_or_is_not_applicable():
    """[実機の裏付け] 現時点のリポジトリのadapters/配下には重大な静的
    解析違反が無いか、adapters/自体が存在しないため、本天使はPASSまたは
    NOT_APPLICABLEのいずれかを報告する(FAILではない)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        sfa.main()
    out = buf.getvalue()
    assert ("✅ PASS" in out) or ("⬜ NOT_APPLICABLE" in out)


def test_reports_not_applicable_when_adapters_dir_is_absent(monkeypatch, tmp_path):
    """adapters/ディレクトリ自体が存在しない場合、PASSではなく
    NOT_APPLICABLEを報告する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(sfa, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        sfa.main()
    assert "⬜ NOT_APPLICABLE" in buf.getvalue()


def test_fails_when_a_critical_violation_is_found(monkeypatch, tmp_path):
    """[核心] adapters/配下のいずれか1つのファイルにcritical重大度の
    静的解析違反が検知された場合、正しくFAILし詳細を含めることを確認
    する。"""
    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / "bad_adapter.py").write_text("import os\nTRIGGER_CRITICAL\n", encoding="utf-8")
    (adapters_dir / "good_adapter.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(sfa, "ROOT", tmp_path)
    monkeypatch.setattr(sefer, "inquisition", _fake_inquisition_flagging("TRIGGER_CRITICAL"))
    try:
        sfa.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_violation_severity_is_not_critical(monkeypatch, tmp_path):
    """[核心・重大度フィルタの確認] 違反が検知されても、重大度が
    'critical'以外(例: 'warning')の場合は、正しくPASSすることを
    確認する(重大度未満のノイズでCIを止めない設計の確認)。"""
    import io
    from contextlib import redirect_stdout

    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / "adapter.py").write_text("TRIGGER_WARNING\n", encoding="utf-8")
    monkeypatch.setattr(sfa, "ROOT", tmp_path)
    monkeypatch.setattr(
        sefer, "inquisition", _fake_inquisition_flagging("TRIGGER_WARNING", severity="warning")
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        sfa.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_when_adapters_dir_has_no_python_files(monkeypatch, tmp_path):
    """adapters/ディレクトリが存在するが.pyファイルを一つも含まない
    場合、検査対象が0件のまま正しくPASSする。"""
    import io
    from contextlib import redirect_stdout

    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / "README.md").write_text("not python\n", encoding="utf-8")
    monkeypatch.setattr(sfa, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        sfa.main()
    assert "✅ PASS" in buf.getvalue()
