"""
tests/test_cherubim_ebpf_guard.py
=====================================
[新設 2026-11] angels/cherubim_ebpf_guard.py の単体テスト。

本天使(「ケルビムの境界」)は、`sys.addaudithook`によるMichael's Sword
(_michael_absolute_defense)が実際に登録・機能していることを、カナリア
攻撃(`os.system('echo canary')`)を実行させて遮断されるかどうかで間接
的に検証する。CPythonにはフックの登録状態を直接確認する手段が無いため、
実際に遮断が機能することそのものを健全性チェックとして用いている。

`run_code_against_sefer`という下層ヘルパー自体の正しさは他のテストで
検証済みだが、本天使固有の「遮断されなければ致命的FAIL」という判定
ロジック自体は、天使群のテストカバレッジの棚卸しの過程で、専用テストが
一件も存在しないことが判明した。ランタイム監視の生死そのものを守る
最も基礎的な天使であるため、優先して対応する。

`cherubim_ebpf_guard.py`は`run_code_against_sefer`をモジュールレベルで
直接importしているため、`cherubim_ebpf_guard.run_code_against_sefer`を
そのままmonkeypatchして、実際のsefer起動を介さずに判定ロジックのみを
検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import cherubim_ebpf_guard as ceg


def test_real_repository_passes():
    """[実機の裏付け] 現時点の実装では、カナリア攻撃が実際にsefer経由で
    遮断されるため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        ceg.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_when_canary_attack_is_blocked(monkeypatch):
    """カナリア攻撃が遮断された(blocked=True)と報告される場合、正しく
    PASSすることを確認する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(ceg, "run_code_against_sefer", lambda code: (True, None))
    buf = io.StringIO()
    with redirect_stdout(buf):
        ceg.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_canary_attack_is_not_blocked(monkeypatch):
    """[核心・致命的フェイルオープン検知] カナリア攻撃が遮断されな
    かった(blocked=False、audit hookが機能していない)場合、正しく
    FAIL(sys.exit(1))することを確認する。"""
    monkeypatch.setattr(ceg, "run_code_against_sefer", lambda code: (False, None))
    try:
        ceg.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1
