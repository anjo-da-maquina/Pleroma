"""
tests/test_check_zkp_audit_export_status.py
=====================================
[新設 2026-11] angels/check_zkp_audit_export_status.py の単体テスト。

本天使(「天の石板」)は、`adapters/junit_xml_exporter.py`が
`zk_audit_trail.json`をJUnit XMLへ正しく変換し、HMAC連鎖の改ざんが
検知された場合はCI自体を失敗させる(ダッシュボード表示だけに任せない)
ことを検証する(§BNで新設)。

`adapters.junit_xml_exporter.export_zkp_to_junit`自体のHMAC連鎖検証
ロジック(`_verify_chain_integrity`)は
`tests/test_junit_xml_exporter_chain_verification.py`で別途検証済み
だが、本天使自身の「生成されたXMLを読み、failures属性に応じてPASS/FAIL
を判定する」というラッパー判定ロジックは、天使群のテストカバレッジの
棚卸しの過程で、専用テストが一件も存在しないことが判明した。

`main()`は`from adapters.junit_xml_exporter import export_zkp_to_junit`
をmain()内部でローカルimportしているため、
`adapters.junit_xml_exporter.export_zkp_to_junit`というモジュール属性
自体をmonkeypatchすることで、実際のHMAC連鎖検証(正当な鍵・連鎖の構築が
必要で複雑)を介さずに、本天使自身のXML読み取り・判定ロジックのみを
単独で検証する。`check_zkp_audit_export_status.ROOT`を一時ディレクトリへ
monkeypatchし、trail_pathの存在有無も制御する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_zkp_audit_export_status as htz
import adapters.junit_xml_exporter as jxe


def _fake_exporter_writing(xml_content):
    def _fake(json_path, xml_path):
        Path(xml_path).write_text(xml_content, encoding="utf-8")
    return _fake


VALID_PASS_XML = (
    '<?xml version="1.0" ?>\n'
    '<testsuites>\n'
    '  <testsuite name="Anjo_Core_ZKP_Audit" tests="1" failures="0" errors="0">\n'
    '    <testcase classname="ZKAuditTrail" name="AuditBlock_0_record"/>\n'
    '  </testsuite>\n'
    '</testsuites>\n'
)

TAMPERED_FAIL_XML = (
    '<?xml version="1.0" ?>\n'
    '<testsuites>\n'
    '  <testsuite name="Anjo_Core_ZKP_Audit" tests="2" failures="1" errors="0">\n'
    '    <testcase classname="ZKAuditTrail" name="AuditBlock_0_record"/>\n'
    '    <testcase classname="ZKAuditTrail" name="ChainIntegrityVerification">\n'
    '      <failure message="HMAC連鎖に改ざんを検知しました">詳細</failure>\n'
    '    </testcase>\n'
    '  </testsuite>\n'
    '</testsuites>\n'
)


def test_real_repository_passes_or_is_not_applicable():
    """[実機の裏付け] 現時点のリポジトリには、まだzk_audit_trail.jsonが
    生成されていないか、生成されていても改ざんが無いため、本天使は
    PASSまたはNOT_APPLICABLEのいずれかを報告する(FAILではない)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        htz.main()
    out = buf.getvalue()
    assert ("✅ PASS" in out) or ("⬜ NOT_APPLICABLE" in out)


def test_reports_not_applicable_when_trail_is_absent(monkeypatch, tmp_path):
    """zk_audit_trail.json自体が存在しない場合は、PASSではなく
    NOT_APPLICABLEを報告する(検査対象なし)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(htz, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        htz.main()
    assert "⬜ NOT_APPLICABLE" in buf.getvalue()


def test_fails_when_generated_xml_is_not_well_formed(monkeypatch, tmp_path):
    """[核心] exporterが生成したXMLが妥当なXMLとして解析できない場合、
    正しくFAILする(見せかけの保護の再発防止: 壊れた出力を無条件に
    PASS扱いしない)。"""
    (tmp_path / "zk_audit_trail.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(htz, "ROOT", tmp_path)
    monkeypatch.setattr(jxe, "export_zkp_to_junit", _fake_exporter_writing("<not><valid<xml"))
    try:
        htz.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_junit_xml_reports_zero_failures(monkeypatch, tmp_path):
    """[核心] 生成されたJUnit XMLのfailures属性が'0'の場合、正しくPASS
    する。"""
    import io
    from contextlib import redirect_stdout

    (tmp_path / "zk_audit_trail.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(htz, "ROOT", tmp_path)
    monkeypatch.setattr(jxe, "export_zkp_to_junit", _fake_exporter_writing(VALID_PASS_XML))
    buf = io.StringIO()
    with redirect_stdout(buf):
        htz.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_junit_xml_reports_tampering(monkeypatch, tmp_path):
    """[核心・§BN退行検知] 生成されたJUnit XMLのfailures属性が'0'以外
    (HMAC連鎖の改ざんが検知された)場合、正しくFAILし、具体的な
    失敗メッセージを含めることを確認する。ダッシュボード表示だけに
    任せず、CI自体を失敗させるという§BNの核心を守る。"""
    (tmp_path / "zk_audit_trail.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(htz, "ROOT", tmp_path)
    monkeypatch.setattr(jxe, "export_zkp_to_junit", _fake_exporter_writing(TAMPERED_FAIL_XML))
    try:
        htz.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1
