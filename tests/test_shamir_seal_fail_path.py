"""
tests/test_shamir_seal_fail_path.py
=====================================
[脆弱性修正 2026-10 §BP] angels/shamir_seal.py の回帰テスト。

angels/shamir_seal.pyは、証明書の有効期限切れを「GitHub Actions等の
未承認クラウド環境(IS_UNVERIFIED_CLOUD)では正常」「それ以外(ローカル等)
では異常」として、異なる2つの分岐(report_pass / report_fail)に振り分ける
設計である。これ自体は`test_sanctuary.py`のゼロトラスト思想と整合する
正当な設計意図だが、本リポジトリには、この2分岐のうち
「IS_UNVERIFIED_CLOUDがFalseの場合に、本当にreport_fail(CI失敗)が
発火するか」を直接検証する専用テストが一件も存在していなかった
(angels/shamir_seal.pyを対象とするテストファイル自体が無かった)。

これは§BM(CHAOS_MODE)・§BN(HMAC連鎖)と構造的に同じ「安全装置が本当に
発火するかを誰も確認していない」というパターンの、未発見だった具体例
である。§11.8/§11.9で設計した「陣性経路テスト必須化」の考え方を、
angels/thrones_positive_path.py という新天使を実装する前に、人間の
依頼に基づく手動のレッドチーム作業(既存の全os.getenv/os.environ.get
利用箇所を洗い出し、各分岐に対応するテストの有無を確認する)によって
実際に発見した。
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import shamir_seal as ss


def _expired_cert(hours_ago: int = 1):
    from datetime import datetime, timedelta, timezone
    expired = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {"payload": {"valid_until": expired.isoformat().replace("+00:00", "Z")}}


def _valid_cert(hours_from_now: int = 999):
    from datetime import datetime, timedelta, timezone
    valid_until = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    return {"payload": {"valid_until": valid_until.isoformat().replace("+00:00", "Z")}}


def test_expired_cert_fails_outside_github_actions(monkeypatch):
    """[核心・§BP] IS_UNVERIFIED_CLOUD=False(ローカル等)で証明書が
    失効している場合、report_fail(SystemExit(1))が実際に発火すること。
    これが修正前は、どのテストでも一度も検証されていなかった。"""
    monkeypatch.setattr(ss, "load_json", lambda path: _expired_cert())
    monkeypatch.setattr(ss, "IS_UNVERIFIED_CLOUD", False)

    try:
        ss.main()
        assert False, "失効した証明書なのにreport_failが発火しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_expired_cert_passes_inside_github_actions(monkeypatch):
    """[回帰防止] IS_UNVERIFIED_CLOUD=True(CI等)では、証明書失効は
    設計上正常な状態としてPASSし続けること。"""
    monkeypatch.setattr(ss, "load_json", lambda path: _expired_cert())
    monkeypatch.setattr(ss, "IS_UNVERIFIED_CLOUD", True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        ss.main()
    assert "✅ PASS" in buf.getvalue()


def test_valid_cert_passes_outside_github_actions(monkeypatch):
    """[回帰防止] 有効な証明書は、IS_UNVERIFIED_CLOUDの値に関わらずPASSし
    続けること(過剰検知の回帰防止)。"""
    monkeypatch.setattr(ss, "load_json", lambda path: _valid_cert())
    monkeypatch.setattr(ss, "IS_UNVERIFIED_CLOUD", False)

    buf = io.StringIO()
    with redirect_stdout(buf):
        ss.main()
    assert "✅ PASS" in buf.getvalue()
