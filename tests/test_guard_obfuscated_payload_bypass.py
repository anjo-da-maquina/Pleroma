"""
tests/test_guard_obfuscated_payload_bypass.py
=====================================
[新設 2026-11] angels/guard_obfuscated_payload_bypass.py の単体テスト。

本天使(「カマエルの盾」)は、難読化された攻撃パターン(OBFUSCATED_ATTACKS)
が、Gabriel(静的解析: `inquisition_catches`)かMichael(動的実行:
`run_code_against_sefer`)のいずれかで必ず捕捉されることを検証する
(両方を素通りした場合のみFAIL、という「多層防御のどちらかで捕捉できれば
よい」というOR条件のラッパー判定ロジック)。

`inquisition_catches`・`run_code_against_sefer`という2つの下層ヘルパー
自体の正しさは、他のテスト(test_sefer系・各天使のテスト)で別途検証
されている。本天使固有の価値は、その2つの結果を受けて「両方突破された
場合のみ失敗する」というOR判定そのものにあるが、天使群のテストカバレッジ
の棚卸しの過程で、この判定ロジック自体を直接検証するテストが一件も
存在しないことが判明した。

`guard_obfuscated_payload_bypass.py`は`inquisition_catches`・`run_code_against_sefer`を
モジュールレベルで直接importしているため、`guard_obfuscated_payload_bypass.inquisition_catches`・
`guard_obfuscated_payload_bypass.run_code_against_sefer`をそのままmonkeypatchして、下層の
実際の検査を介さずに判定ロジックのみを検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import guard_obfuscated_payload_bypass as cs


def test_real_repository_passes():
    """[実機の裏付け] 現時点の実装では、全ての難読化攻撃パターンが静的
    または動的検査のいずれかで捕捉されるため、本天使はPASSを報告
    する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        cs.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_when_all_attacks_caught_statically_only(monkeypatch):
    """静的検査(Gabriel相当)のみが全攻撃を捕捉し、動的検査が常に
    捕捉できない(blocked_dynamically=False)場合でも、OR条件によりPASS
    することを確認する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(cs, "inquisition_catches", lambda code: True)
    monkeypatch.setattr(cs, "run_code_against_sefer", lambda code: (False, None))
    buf = io.StringIO()
    with redirect_stdout(buf):
        cs.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_when_all_attacks_caught_dynamically_only(monkeypatch):
    """動的検査(Michael相当)のみが全攻撃を捕捉し、静的検査が常に捕捉
    できない(caught_statically=False)場合でも、OR条件によりPASSする
    ことを確認する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(cs, "inquisition_catches", lambda code: False)
    monkeypatch.setattr(cs, "run_code_against_sefer", lambda code: (True, None))
    buf = io.StringIO()
    with redirect_stdout(buf):
        cs.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_one_attack_bypasses_both_layers(monkeypatch):
    """[核心] いずれか1件の攻撃が静的・動的どちらにも捕捉されない場合、
    正しくFAIL(sys.exit(1))することを確認する。"""
    monkeypatch.setattr(cs, "inquisition_catches", lambda code: False)
    monkeypatch.setattr(cs, "run_code_against_sefer", lambda code: (False, None))
    try:
        cs.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_attacks_list_is_not_accidentally_emptied():
    """[構造的フェイルオープン検知] `OBFUSCATED_ATTACKS`が将来誤って
    空リストにされた場合、検査対象が無いままループが即終了し空虚な
    PASSになる(偽の安全)という構造的リスクを監視する。空でないことを
    直接固定しておく。"""
    assert len(cs.OBFUSCATED_ATTACKS) > 0
