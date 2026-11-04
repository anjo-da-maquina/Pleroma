"""
tests/test_guard_sandbox_core_attack_battery.py
=====================================
[新設 2026-11] angels/guard_sandbox_core_attack_battery.py の単体テスト。

本天使(「ミカエルの剣」)は、`ATTACKS`に列挙された既知の攻撃パターン
(プロセス起動・無許可書き込み・破壊的なファイル削除)が、実際に
`run_code_against_sefer()`経由でSanctum配下に投げられたときに、確実に
遮断されることを検証する。`run_code_against_sefer()`自体の正しさは
他の天使のテストでも間接的に使われているが、本天使固有の「`ATTACKS`
リストの全件が遮断されたかを確認し、1件でも漏れていればFAILにする」
という判定ロジック自体は、天使群のテストカバレッジの棚卸しの過程で、
本天使を直接実行する専用テストが一件も存在しないことが判明した。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import guard_sandbox_core_attack_battery as ms


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、ATTACKSの全件が実際に
    Sanctumで遮断されるため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        ms.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_any_attack_is_not_blocked(monkeypatch):
    """[核心] ATTACKSのうち1件でも遮断されなかった(=`run_code_against_
    sefer`がblocked=Falseを返した)場合、本天使が正しくFAIL
    (sys.exit(1))することを確認する。"""
    calls = {"n": 0}

    def fake_run_code_against_sefer(code, allowed_dirs=None, allowed_hosts=None):
        calls["n"] += 1
        # 最初の1件だけ「遮断されなかった」ことにする(退行の模擬)。
        if calls["n"] == 1:
            return False, "模擬: 遮断されなかった"
        return True, ""

    monkeypatch.setattr(ms, "run_code_against_sefer", fake_run_code_against_sefer)
    try:
        ms.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_no_attacks_are_blocked(monkeypatch):
    """ATTACKS全件が遮断されなかった(深層防御が完全に機能していない
    最悪の状態)場合も、当然FAILする。"""
    monkeypatch.setattr(
        ms, "run_code_against_sefer",
        lambda code, allowed_dirs=None, allowed_hosts=None: (False, "模擬"),
    )
    try:
        ms.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_all_attacks_are_blocked(monkeypatch):
    """ATTACKS全件が正しく遮断された場合は、想定どおりPASSする
    (回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(
        ms, "run_code_against_sefer",
        lambda code, allowed_dirs=None, allowed_hosts=None: (True, ""),
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        ms.main()
    assert "✅ PASS" in buf.getvalue()


def test_attacks_list_is_not_accidentally_emptied():
    """[退行防止] `ATTACKS`が将来誤って空リストに変更された場合、
    `main()`はforループが一度も実行されずに無条件でPASSを報告してしまう
    (=検査が実質的に無効化される)。本テストは、現時点で`ATTACKS`が
    空でないことを固定し、将来の静かな無効化を検知する。"""
    assert len(ms.ATTACKS) > 0
