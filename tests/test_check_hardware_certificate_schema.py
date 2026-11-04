"""
tests/test_check_hardware_certificate_schema.py
=====================================
[新設 2026-11] angels/check_hardware_certificate_schema.py の単体テスト。

本天使(「メタトロンの立方体」)は、ハードウェア証明書
(`ataraxia_certificate.json`)の署名ペイロードに必須フィールド
(`client_id`・`hardware_fingerprint`・`valid_until`)および`signature`
フィールドが揃っているかを検証する(実HSM未接続のため、フォーマットの
健全性チェックに留める設計)。天使群のテストカバレッジの棚卸しの過程
で、専用テストが一件も存在しないことが判明した。

`load_json`はモジュールレベルで直接importされているため、
`check_hardware_certificate_schema.load_json`自体をmonkeypatchして、実際のファイル
I/Oを介さずに判定ロジックのみを検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import check_hardware_certificate_schema as mch

VALID_CERT = {
    "payload": {
        "client_id": "c1",
        "hardware_fingerprint": "abc123",
        "valid_until": "2027-01-01",
    },
    "signature": "deadbeef",
}


def test_real_repository_passes_or_is_not_applicable():
    """[実機の裏付け] 現時点のリポジトリには、まだ証明書が発行されて
    いないか、発行済みで正しい形式であるため、本天使はPASSまたは
    NOT_APPLICABLEのいずれかを報告する(FAILではない)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        mch.main()
    out = buf.getvalue()
    assert ("✅ PASS" in out) or ("⬜ NOT_APPLICABLE" in out)


def test_reports_not_applicable_when_certificate_is_absent(monkeypatch):
    """証明書自体が未発行(load_jsonがNoneを返す)場合は、PASSではなく
    NOT_APPLICABLEを報告する。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(mch, "load_json", lambda path: None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        mch.main()
    assert "⬜ NOT_APPLICABLE" in buf.getvalue()


def test_fails_when_required_payload_field_is_missing(monkeypatch):
    """[核心] payload内の必須フィールド(例: hardware_fingerprint)が
    欠落している場合、正しくFAILする。"""
    bad_cert = {
        "payload": {"client_id": "c1", "valid_until": "2027-01-01"},
        "signature": "deadbeef",
    }
    monkeypatch.setattr(mch, "load_json", lambda path: bad_cert)
    try:
        mch.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_payload_key_itself_is_absent(monkeypatch):
    """payloadキー自体が証明書JSONに存在しない場合も、全必須フィールド
    欠落として正しくFAILする。"""
    bad_cert = {"signature": "deadbeef"}
    monkeypatch.setattr(mch, "load_json", lambda path: bad_cert)
    try:
        mch.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_fails_when_signature_field_is_missing(monkeypatch):
    """[核心] payloadの必須フィールドは揃っていても、signatureフィールド
    自体が証明書に無い場合、正しくFAILする。"""
    bad_cert = {"payload": dict(VALID_CERT["payload"])}
    monkeypatch.setattr(mch, "load_json", lambda path: bad_cert)
    try:
        mch.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_with_all_required_fields_present(monkeypatch):
    """必須フィールド・signatureのいずれも揃っていれば、想定どおり
    PASSする(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(mch, "load_json", lambda path: VALID_CERT)
    buf = io.StringIO()
    with redirect_stdout(buf):
        mch.main()
    assert "✅ PASS" in buf.getvalue()
