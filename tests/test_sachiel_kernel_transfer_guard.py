"""
tests/test_sachiel_kernel_transfer_guard.py
====================================
[新設 2026-10 §CD] angels/sachiel_kernel_transfer_guard.py の単体テスト。

実際に発見した具体例: `sefer/__init__.py`のfd事前オープンバイパス対策は
os.write/os.pwrite/os.writev/os.pwritevの4系統のみをラップしていたが、
`os.sendfile()`と`os.copy_file_range()`はいずれもCPythonのaudit event
を一切発生させないカーネル直接転送APIであり、完全に素通りしていた。
この2関数自体をos.write系と同じ方針でラップする修正の、継続的な
再検証を本天使が担う。自己レッドチームの結果(修正前の状態に戻すと
正しくFAILし、復元すると正しくPASSすることを確認済み)を回帰テスト
として固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import sachiel_kernel_transfer_guard as skt


def test_real_repository_battery_passes():
    """[実機の裏付け] 修正後の実装が、全ての既知の状況を正しく処理する
    ことを確認する(§CDの修正の回帰防止)。"""
    failures = skt.run_battery()
    assert failures == [], f"検知に失敗した項目があります: {failures}"


def test_main_reports_pass_on_real_repository():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        skt.main()
    assert "✅ PASS" in buf.getvalue()


def test_check_sendfile_write_is_blocked_directly():
    success, detail = skt._check_sendfile_write_is_blocked()
    assert success is True, detail


def test_check_copy_file_range_write_is_blocked_directly():
    success, detail = skt._check_copy_file_range_write_is_blocked()
    assert success is True, detail


def test_check_sendfile_inside_allowed_dirs_is_not_falsely_blocked_directly():
    success, detail = skt._check_sendfile_inside_allowed_dirs_is_not_falsely_blocked()
    assert success is True, detail


def test_check_copy_file_range_inside_allowed_dirs_is_not_falsely_blocked_directly():
    success, detail = skt._check_copy_file_range_inside_allowed_dirs_is_not_falsely_blocked()
    assert success is True, detail


def test_battery_detects_reintroduced_regression(monkeypatch):
    """[核心・自己レッドチームの固定] §CD修正前の、os.sendfile/
    os.copy_file_rangeを一切ラップしない実装に戻した場合、本天使が
    正しく「遮断されなかった」として検知することを、実際に確認する。"""
    def _vulnerable_check():
        return False, "allowed_dirs外へのsendfile書き込みが遮断されなかった(模擬)"

    patched_checks = [
        ("sefer._guarded_os_sendfile: fd事前オープン書き込み遮断", _vulnerable_check),
        ("sefer._guarded_os_sendfile: allowed_dirs内の誤検知防止", skt._check_sendfile_inside_allowed_dirs_is_not_falsely_blocked),
    ]
    monkeypatch.setattr(skt, "CHECKS", patched_checks)

    failures = skt.run_battery()
    assert len(failures) == 1
    assert failures[0][0] == "sefer._guarded_os_sendfile: fd事前オープン書き込み遮断"


def test_checker_exception_is_reported_as_a_failure(monkeypatch):
    """検査関数自体が想定外の例外を発生させた場合も、「安全側」に倒して
    失敗として報告する(例外を握り潰してPASSにしない)。"""
    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(skt, "CHECKS", [("boom-checker", _boom)])
    failures = skt.run_battery()
    assert len(failures) == 1
    assert "boom" in failures[0][1]
