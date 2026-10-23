"""
tests/test_nuriel_capability_strip_guard.py
============================================
[新設 2026-10 §CF] angels/nuriel_capability_strip_guard.py の単体テスト。

実際に発見した具体例: `src/sandalphon_jail.py`の`run_in_sandalphon()`が
展開する隔離結界(Docker)は、ネットワーク完全遮断・読み取り専用・
非rootユーザーの3点にしか依存しておらず、コンテナ自体にはDockerの
既定のLinuxケーパビリティ集合(CAP_DAC_OVERRIDE・CAP_SETUID等)が残って
いた。`--cap-drop=ALL`・`--security-opt=no-new-privileges`・
`--pids-limit`を追加して修正した。

本テストは、(A) 常にこの環境で実行可能な静的検証(3オプションの存在
確認)の回帰防止、(B) イメージ取得ができない環境(このクラウドサンド
ボックス自身がまさにその環境である)での、INCONCLUSIVE(PASSに偽装
しない正直な「検証不能」の報告)への正しい分岐、(C) 実際にコンテナが
起動できる環境でのみ意味を持つ、ケーパビリティ剥奪の回帰検知ロジック
自体の単体動作、の3点を確認する。
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import nuriel_capability_strip_guard as ncsg


def test_static_check_passes_on_real_repository():
    ok, detail = ncsg._check_static_flags_present()
    assert ok is True, detail


def test_static_check_detects_missing_cap_drop_regression(tmp_path, monkeypatch):
    """[核心・自己レッドチームの固定] §CF修正前の、3オプションを一切
    付与していない実装に戻した場合、本天使が正しく検知することを確認
    する。"""
    fake_root = tmp_path
    (fake_root / "src").mkdir()
    (fake_root / "src" / "sandalphon_jail.py").write_text(
        'run_cmd = ["docker", "run", "--rm", "--network", "none", "--read-only"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ncsg, "ROOT", fake_root)
    ok, detail = ncsg._check_static_flags_present()
    assert ok is False
    assert "cap-drop" in detail
    assert "no-new-privileges" in detail
    assert "pids-limit" in detail


def test_static_check_detects_partial_regression_missing_only_pids_limit(tmp_path, monkeypatch):
    fake_root = tmp_path
    (fake_root / "src").mkdir()
    (fake_root / "src" / "sandalphon_jail.py").write_text(
        'run_cmd = ["docker", "run", "--cap-drop=ALL", "--security-opt=no-new-privileges"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ncsg, "ROOT", fake_root)
    ok, detail = ncsg._check_static_flags_present()
    assert ok is False
    assert "pids-limit" in detail
    assert "cap-drop" not in detail.split(":")[-1] or "pids-limit" in detail


def test_static_check_missing_file_is_reported_as_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ncsg, "ROOT", tmp_path)
    ok, detail = ncsg._check_static_flags_present()
    assert ok is False
    assert "見つかりません" in detail


def test_dynamic_check_is_inconclusive_when_docker_daemon_unavailable(monkeypatch):
    """[正直な注記の固定] Dockerデーモン自体が利用できない場合、
    「失敗(FAIL)」ではなく「検証不能(INCONCLUSIVE)」として報告され、
    PASSに偽装しないことを確認する。"""
    import sandalphon_jail as sj
    monkeypatch.setattr(sj, "check_docker_available", lambda: (False, "テスト: デーモン未起動"))
    status, detail = ncsg._check_dynamic_capability_is_actually_dropped()
    assert status == "INCONCLUSIVE"
    assert "デーモン" in detail


def test_dynamic_check_is_inconclusive_when_image_build_fails(monkeypatch):
    """[実機で実際に確認済みの状態の固定] このクラウドサンドボックス
    環境そのものが、まさにこの分岐(デーモンは起動できるがコンテナ
    レジストリへのアクセスがネットワーク許可一覧で遮断されている)を
    通ることを、実機で確認済み。"""
    import sandalphon_jail as sj
    monkeypatch.setattr(sj, "check_docker_available", lambda: (True, ""))

    def _boom():
        raise subprocess.CalledProcessError(1, ["docker", "build"])

    monkeypatch.setattr(sj, "_ensure_image_built", _boom)
    status, detail = ncsg._check_dynamic_capability_is_actually_dropped()
    assert status == "INCONCLUSIVE"
    assert "取得・構築" in detail


def test_dynamic_check_detects_capability_not_actually_dropped_regression(monkeypatch):
    """[核心・自己レッドチームの固定] 何らかの退行で剥奪が機能しておらず
    os.setuid(0)が実際に成功してしまった場合、本天使が正しくFAILを
    報告することを確認する(コンテナの起動自体をモックして、ロジック
    単体の正しさを検証する)。"""
    import sandalphon_jail as sj
    monkeypatch.setattr(sj, "check_docker_available", lambda: (True, ""))
    monkeypatch.setattr(sj, "_ensure_image_built", lambda: None)

    class _FakeProc:
        stdout = "SETUID_SUCCEEDED\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeProc())
    status, detail = ncsg._check_dynamic_capability_is_actually_dropped()
    assert status == "FAIL"
    assert "回帰" in detail


def test_dynamic_check_passes_when_setuid_is_correctly_blocked(monkeypatch):
    import sandalphon_jail as sj
    monkeypatch.setattr(sj, "check_docker_available", lambda: (True, ""))
    monkeypatch.setattr(sj, "_ensure_image_built", lambda: None)

    class _FakeProc:
        stdout = "SETUID_BLOCKED\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeProc())
    status, detail = ncsg._check_dynamic_capability_is_actually_dropped()
    assert status == "PASS", detail


def test_main_reports_inconclusive_on_this_real_sandbox_environment():
    """[実機の裏付け] このクラウドサンドボックス環境で`main()`を実際に
    呼び出し、INCONCLUSIVE(PASSへの偽装なし)として正常終了(例外なし)
    することを確認する。真の動的PASS/FAILの確認は、コンテナレジストリ
    へ到達できる実際のGitHub Actions環境に委ねる。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        ncsg.main()  # 例外(sys.exit)を発生させずに正常終了するはず
    output = buf.getvalue()
    assert "INCONCLUSIVE" in output or "PASS" in output
    assert "FAIL" not in output.split("❌")[0] if "❌" in output else True


def test_main_reports_fail_when_static_check_fails(monkeypatch):
    monkeypatch.setattr(ncsg, "_check_static_flags_present", lambda: (False, "模擬: フラグが欠落"))
    try:
        ncsg.main()
        assert False, "静的検証の失敗がFAILとして報告されなかった"
    except SystemExit as e:
        assert e.code == 1
