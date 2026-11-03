"""
tests/test_seraphim_consensus.py
=====================================
[新設 2026-11] angels/seraphim_consensus.py の単体テスト。

本天使(「セラフィムの合意」)は、危険なコード片に対する判定が、単一の
検査レイヤー(静的AST解析のみ、または動的監査フックのみ)だけに依存して
いないか――すなわち、Gabriel(静的)とSefer.Sanctum(動的)という独立した
2つのレイヤーが、実際に合意して初めて「危険」と判定する多層防御の構造に
なっているか――を検証する。

本ファイルの新設以前、本天使には専用のテストが一件も存在せず(天使群の
テストカバレッジの棚卸しで発見)、`main()`のpass/fail判定ロジック自体が
退行しても、どのテストも検知できない状態だった。`inquisition_catches`・
`run_code_against_sefer`という共有ヘルパー自体は他のテストファイルで
間接的に検証されているが、本天使自身の「両方合意しなければFAILにする」
という判定ロジックは、本天使を直接実行するテストでなければ固定できない。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import seraphim_consensus as sc


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、静的解析(Gabriel)・動的
    監査フック(Sefer.Sanctum)の両方が独立して危険コードを検知するため、
    本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        sc.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_only_static_layer_agrees(monkeypatch):
    """[核心] 動的監査フック(Sefer.Sanctum)が危険コードを検知しなく
    なった(=静的解析のみに実質的に依存する状態に退行した)場合、本天使が
    正しくFAIL(sys.exit(1))することを確認する。"""
    monkeypatch.setattr(sc, "inquisition_catches", lambda code: True)
    monkeypatch.setattr(sc, "run_code_against_sefer", lambda code: (False, ""))
    try:
        sc.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_only_dynamic_layer_agrees(monkeypatch):
    """[核心] 静的解析(Gabriel)が危険コードを検知しなくなった(=動的
    監査フックのみに実質的に依存する状態に退行した)場合も、同様に本天使
    が正しくFAILすることを確認する。"""
    monkeypatch.setattr(sc, "inquisition_catches", lambda code: False)
    monkeypatch.setattr(sc, "run_code_against_sefer", lambda code: (True, ""))
    try:
        sc.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_neither_layer_agrees(monkeypatch):
    """両方のレイヤーが一致して検知に失敗した場合(多層防御が完全に
    機能していない最悪の状態)も、当然FAILする。"""
    monkeypatch.setattr(sc, "inquisition_catches", lambda code: False)
    monkeypatch.setattr(sc, "run_code_against_sefer", lambda code: (False, ""))
    try:
        sc.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_both_layers_agree(monkeypatch):
    """両方のレイヤーが一致して正しく検知した場合は、想定どおりPASSする
    (回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(sc, "inquisition_catches", lambda code: True)
    monkeypatch.setattr(sc, "run_code_against_sefer", lambda code: (True, ""))
    buf = io.StringIO()
    with redirect_stdout(buf):
        sc.main()
    assert "✅ PASS" in buf.getvalue()
