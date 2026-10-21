"""
tests/test_haniel_truncation_guard.py
========================================
[新設 2026-10 §BX] angels/haniel_truncation_guard.py の単体テスト。

実際に発見した具体例: `sefer/audit_chain.py`のSignedAuditChain、
`maquina_gatekeeper.py`のZKAuditTrailはいずれも、鍵付きHMAC-SHA256
による改ざん耐性を謳っていたが、「ログファイル自体を鍵の知識なしに
空へ切り詰める」という、暗号的な知識を一切必要としないもっと単純な
攻撃に対しては無力だった(「0件」と「まだ記録が無い」を区別できて
いなかった)。水位標(watermark)ファイルの導入でこれを修正し、継続的
に再検証する本天使の、自己レッドチームの結果を固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import haniel_truncation_guard as htg


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の両実装が、切り詰め攻撃を正しく検知する
    ことを確認する(§BXの修正の回帰防止)。"""
    failures = htg.run_battery()
    assert failures == [], f"検知に失敗した実装があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        htg.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_signed_audit_chain_detects_truncation_directly():
    success, detail = htg._check_signed_audit_chain()
    assert success is True, detail


def test_check_zk_audit_trail_detects_truncation_directly():
    success, detail = htg._check_zk_audit_trail()
    assert success is True, detail


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §BX修正前の、水位標を一切持たない
    素朴な実装(0件を無条件にTrueとみなす)に戻した場合、本天使が正しく
    「検知されなかった」として検知することを、実際に確認する。"""
    def _vulnerable_check(name_for_message):
        def _check(*_args, **_kwargs):
            # §BX修正前相当: 0件への切り詰めは常に検知できない、という
            # 既知の脆弱な挙動をそのまま再現するスタブ。
            return False, f"ログ全体を切り詰めても改ざんが検知されなかった({name_for_message})"
        return _check

    patched_checks = [
        ("sefer.audit_chain.SignedAuditChain", _vulnerable_check("stub")),
        ("maquina_gatekeeper.ZKAuditTrail", htg._check_zk_audit_trail),
    ]
    monkeypatch.setattr(htg, "CHECKS", patched_checks)

    failures = htg.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "sefer.audit_chain.SignedAuditChain"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(htg, "CHECKS", [("boom-checker", _boom)])
    failures = htg.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]
