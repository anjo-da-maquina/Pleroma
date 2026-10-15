import json
import os
import sys
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


def _verify_chain_integrity(trail):
    """zk_audit_trail.jsonのHMAC連鎖を実際に再検証する。改ざんが無ければ
    Noneを、検知された場合はエラーメッセージ文字列を返す。

    [脆弱性修正 2026-10 §BN] 本関数が追加される前は、export_zkp_to_junit()
    はこの検証を一切行わず、常にfailures="0"を出力していた。詳細は
    export_zkp_to_junit()のdocstring参照。"""
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from maquina_gatekeeper import ZKAuditTrail
        key = ZKAuditTrail._get_key()
        ZKAuditTrail._verify_full_chain(trail, key)
        return None
    except Exception as e:
        return str(e)


def export_zkp_to_junit(json_path="zk_audit_trail.json", xml_path="zk_audit_report.xml"):
    """
    ZKP監査ログを読み込み、CI/CDダッシュボードが解釈可能な
    JUnit XML形式へと変換する。

    [脆弱性修正 2026-10 §BN] 以前の実装は、testsuiteのfailures/errors
    属性を常に"0"で固定しており、zk_audit_trail.jsonのHMAC連鎖が実際に
    改ざんされていた(ハッシュの不整合・連続性の破綻があった)場合でも、
    一切検証せずに常に「全件成功」のJUnitレポートを生成していた。
    CI/CDダッシュボードはこのXMLの内容だけを見るため、根底の監査ログが
    壊れていてもダッシュボード上は常に緑色になる、という見せかけの
    保護だった(GRIMOIRE.md §BN参照)。本修正では、
    maquina_gatekeeper.ZKAuditTrailが備える鍵付きHMAC連鎖検証
    (_verify_full_chain、通常はverify_and_record呼び出し時に毎回実行
    されているものと同一のロジック)を、エクスポート時にも実際に呼び出し、
    改ざんが検知された場合はfailures="1"と、具体的なエラー内容を含む
    <failure>要素を出力するようにした。
    """
    if not os.path.exists(json_path):
        print(f"[XML Exporter] 監査ログ '{json_path}' が存在しません。")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            trail = json.load(f)
        except json.JSONDecodeError:
            print("[XML Exporter] 監査ログの形式が不正です。")
            return

    tamper_error = _verify_chain_integrity(trail)

    testsuites = Element('testsuites')
    testsuite = SubElement(
        testsuites,
        'testsuite',
        name="Anjo_Core_ZKP_Audit",
        tests=str(len(trail) + (1 if tamper_error else 0)),
        failures="1" if tamper_error else "0",
        errors="0"
    )

    for idx, block in enumerate(trail):
        testcase = SubElement(
            testsuite,
            'testcase',
            classname="ZKAuditTrail",
            name=f"AuditBlock_{idx}_{block.get('action')}"
        )
        system_out = SubElement(testcase, 'system-out')
        system_out.text = (
            f"Timestamp: {block.get('timestamp')}\n"
            f"Action: {block.get('action')}\n"
            f"Previous Hash: {block.get('previous_hash')}\n"
            f"Current Hash: {block.get('current_hash')}\n"
            f"Proof: {block.get('zk_proof')}"
        )

    if tamper_error:
        chain_testcase = SubElement(
            testsuite, 'testcase',
            classname="ZKAuditTrail", name="ChainIntegrityVerification",
        )
        failure = SubElement(
            chain_testcase, 'failure',
            message="zk_audit_trail.jsonのHMAC連鎖に改ざんを検知しました",
        )
        failure.text = tamper_error

    xmlstr = minidom.parseString(tostring(testsuites)).toprettyxml(indent="  ")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xmlstr)

    if tamper_error:
        print(f"[XML Exporter] ⚠️ 監査ログの改ざんを検知しました: {tamper_error}")
    print(f"[XML Exporter] 監査記録をJUnit XML（{xml_path}）へ出力しました。")

if __name__ == "__main__":
    export_zkp_to_junit()
