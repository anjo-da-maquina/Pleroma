"""
tests/test_audit_signed_chain_integrity.py
=====================================
[新設 2026-11] angels/audit_signed_chain_integrity.py の単体テスト。

本天使(「ザドキエルの天球儀」)は、署名付き監査チェーン
(`sefer/audit_chain.jsonl`)のハッシュ連鎖が改ざんされていないことを、
`sefer.audit_chain.SignedAuditChain.verify_integrity()`を呼んで検証する。
`verify_integrity()`自体は`tests/test_audit_chain.py`で既に広範に検証
されているが、本天使自身の「`verify_integrity()`がFalseを返したら
report_failでFAILにする」という薄いラッパーのpass/fail判定ロジック
自体は、天使群のテストカバレッジの棚卸しの過程で、本天使を直接実行する
専用テストが一件も存在しないことが判明した。

`SignedAuditChain`は`main()`内のローカルimport(`from sefer.audit_chain
import SignedAuditChain`)で取得されるため、`audit_signed_chain_integrity`モジュール
自身の属性としてはmonkeypatchできない。そのため、`sefer.audit_chain.
SignedAuditChain.verify_integrity`メソッド自体をクラスレベルで一時的に
差し替える方式で検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import audit_signed_chain_integrity as za
from sefer.audit_chain import SignedAuditChain


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリの実際の監査チェーンは改ざん
    されていないため、本天使はPASSを報告する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        za.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_chain_integrity_check_fails(monkeypatch):
    """[核心] `SignedAuditChain.verify_integrity()`がFalse(改ざん検知)
    を返した場合、本天使が正しくFAIL(sys.exit(1))することを確認する。"""
    monkeypatch.setattr(SignedAuditChain, "verify_integrity", lambda self: False)
    try:
        za.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_passes_when_chain_integrity_check_succeeds(monkeypatch):
    """`verify_integrity()`がTrueを返す限り、本天使はPASSする
    (回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    monkeypatch.setattr(SignedAuditChain, "verify_integrity", lambda self: True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        za.main()
    assert "✅ PASS" in buf.getvalue()
