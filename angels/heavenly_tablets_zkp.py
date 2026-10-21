import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, report_not_applicable, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "天の石板 (Heavenly Tablets ZKP)"


# ZKP生成監査: zk_audit_trail.json から JUnit XML へのエクスポートが
# 正しく機能し、生成物が妥当なXMLであることを検証する。
#
# [脆弱性修正 2026-10 §BN] 以前はXMLとして妥当かどうかしか検証しておらず、
# adapters/junit_xml_exporter.pyが改ざん検知の有無に関わらず常に
# failures="0"を出力していた(=見せかけの保護)問題そのものには、本検査は
# 気づけなかった。exporter側の修正(§BN)に合わせ、本検査でも生成された
# JUnit XMLのfailures属性を読み、改ざんが検知されていればCI自体を
# 失敗させるようにする(ダッシュボードだけに任せない)。
def main():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "adapters"))
    trail_path = ROOT / "zk_audit_trail.json"
    if not trail_path.exists():
        report_not_applicable(NAME, "zk_audit_trail.json が未生成のため検査対象なし。")
        return
    from adapters.junit_xml_exporter import export_zkp_to_junit
    out_path = ROOT / "zk_audit_report.xml"
    export_zkp_to_junit(json_path=str(trail_path), xml_path=str(out_path))
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(out_path)
    except ET.ParseError as e:
        report_fail(NAME, f"生成されたZKP監査レポートが妥当なXMLではありません: {e}")
        return
    testsuite = tree.getroot().find("testsuite")
    if testsuite is not None and testsuite.get("failures", "0") != "0":
        failure_messages = [
            f"{tc.get('name')}: {tc.find('failure').get('message')}"
            for tc in testsuite.findall("testcase")
            if tc.find("failure") is not None
        ]
        report_fail(
            NAME,
            f"zk_audit_trail.jsonのHMAC連鎖に改ざんが検知されました: {failure_messages}"
        )
        return
    report_pass(NAME, "ZKP監査レポート(JUnit XML)の生成・妥当性を確認しました。")

if __name__ == "__main__":
    main()
