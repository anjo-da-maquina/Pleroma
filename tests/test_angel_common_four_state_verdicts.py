"""
tests/test_angel_common_four_state_verdicts.py
================================================
[脆弱性修正 2026-10 §BO] angels/_common.py の回帰テスト。

以前の angels/_common.py には report_pass / report_fail の2値しか無く、
「検査対象が存在しない」(NOT_APPLICABLE) ケースを report_pass で代用して
いた angels/*.py が9ファイル存在した(azazel_dependency_audit.py,
heavenly_tablets_zkp.py, metatron_cube_hsm.py, metatron_revelation_mcp.py,
ophanim_thousand_eyes.py, sandalphon_echo.py, sariel_fallen_auditor.py,
shamir_seal.py, uriel_nonce.py)。これはCI上では「全て検査してPASSした」
ように見えるが、実際には何も検査していない、見せかけの緑だった。

本テストは、(1) 新設した report_inconclusive / report_not_applicable が
PASS/FAILとは明確に異なる文字列を出力すること、(2) 両関数が sys.exit() を
呼ばず正常終了すること(実装中の自己訂正: 当初は専用の終了コードで
sys.exit()する設計だったが、.github/workflows/anjo_da_maquina_protocol.yml
の各天使ステップにcontinue-on-errorが存在せず、非ゼロ終了コードはどれも
CIジョブ全体を失敗させてしまうため、通常運用を壊さないよう無修正のまま
sys.exit(1)するFAILとは区別して正常終了するよう設計変更した)、
(3) 実際に9ファイルのうち代表例(heavenly_tablets_zkp.py, uriel_nonce.py)
が、検査対象が存在しない状態で report_pass ではなく
report_not_applicable を呼ぶことを、実機の挙動で固定する。
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import _common as common


def test_report_inconclusive_does_not_exit_and_prints_distinct_marker():
    """[核心] INCONCLUSIVEはCIを止めず(sys.exitしない)、PASSとは異なる
    絵文字付きの行を出力する。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        common.report_inconclusive("TEST", "証拠不十分のため判定不能。")
    out = buf.getvalue()
    assert "INCONCLUSIVE" in out
    assert "✅ PASS" not in out


def test_report_not_applicable_does_not_exit_and_prints_distinct_marker():
    """[核心] NOT_APPLICABLEはCIを止めず(sys.exitしない)、PASSとは異なる
    絵文字付きの行を出力する。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        common.report_not_applicable("TEST", "検査対象が存在しない。")
    out = buf.getvalue()
    assert "NOT_APPLICABLE" in out
    assert "✅ PASS" not in out


def test_report_fail_still_exits_nonzero():
    """[回帰防止] 既存のFAILの挙動(sys.exit(1))は変更しない。"""
    try:
        common.report_fail("TEST", "失敗。")
        assert False, "report_failはSystemExitを発生させるべき"
    except SystemExit as e:
        assert e.code == 1


def test_report_pass_still_does_not_exit():
    """[回帰防止] 既存のPASSの挙動(例外なし)は変更しない。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        common.report_pass("TEST", "成功。")
    assert "✅ PASS" in buf.getvalue()


def test_evidence_kwarg_is_printed_when_given():
    """[§4.3対応] evidence引き次を渡した場合、その内容が出力に含まれる。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        common.report_not_applicable("TEST", "対象なし。", evidence={"checked_path": "/tmp/x"})
    assert "checked_path" in buf.getvalue()


def test_heavenly_tablets_zkp_reports_not_applicable_when_trail_missing(tmp_path, monkeypatch):
    """[§BO核心] zk_audit_trail.jsonが存在しない場合、
    以前はreport_passで「検査対象なし」をPASSと誤報告していた。
    修正後はreport_not_applicableを呼び、CIは落とさず(exit 0)かつ
    PASSとは区別可能な行を出力することを、実機の挙動で固定する。"""
    import importlib
    import heavenly_tablets_zkp as htz
    importlib.reload(htz)
    monkeypatch.setattr(htz, "ROOT", tmp_path)

    buf = io.StringIO()
    with redirect_stdout(buf):
        htz.main()
    out = buf.getvalue()
    assert "NOT_APPLICABLE" in out
    assert "✅ PASS" not in out


def test_uriel_nonce_reports_not_applicable_when_chain_missing(tmp_path, monkeypatch):
    """[§BO核心] 監査チェーンが未生成の場合、以前はPASSと誤報告していた。
    修正後はNOT_APPLICABLEを出力し、CIは落とさない。"""
    import importlib
    import uriel_nonce as un
    importlib.reload(un)
    monkeypatch.setattr(un, "ROOT", tmp_path)

    buf = io.StringIO()
    with redirect_stdout(buf):
        un.main()
    out = buf.getvalue()
    assert "NOT_APPLICABLE" in out
    assert "✅ PASS" not in out
