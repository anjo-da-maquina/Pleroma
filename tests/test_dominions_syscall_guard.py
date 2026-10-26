"""
tests/test_dominions_syscall_guard.py
======================================
[新設 2026-10 §CG] angels/dominions_syscall_guard.py の単体テスト。

実際に発見した具体例: §CFで導入したLinuxケーパビリティの剥奪は
「root相当の特権の有無」を制御するが、「どのシステムコール自体を
呼べるか」は制御しない。§CD・§CEで発見した「Sanctumに入る前に確保済み
のfd・関数ポインタを使った迂回」は、特権を一切必要とせず、無権限プロ
セスのままでも到達できるシステムコールの範疇にある。本テストは、
`src/sandalphon/seccomp-profile.json`(denylist方式のseccompプロファ
イル)・`src/sandalphon_jail.py`からの参照・libseccompによる生カーネル
への直接ロードの3層が、それぞれ正しく機能し、正しく後退を検知する
ことを確認する。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import dominions_syscall_guard as dsg


def test_profile_json_check_passes_on_real_repository():
    ok, detail = dsg._check_profile_json_is_well_formed()
    assert ok is True, detail


def test_docker_run_reference_check_passes_on_real_repository():
    ok, detail = dsg._check_docker_run_references_profile()
    assert ok is True, detail


def test_raw_kernel_enforcement_passes_on_real_repository():
    """[核心・実機での裏付け] Dockerを一切使わず、libseccompを直接
    ロードして、denylist上のシステムコールが実際にこのホストの
    カーネルによってEPERMで拒否され、良性の操作は壊れないことを
    実機で確認する。"""
    status, detail = dsg._check_raw_kernel_enforcement()
    assert status == "PASS", detail


def test_profile_json_check_detects_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dsg, "_PROFILE_PATH", tmp_path / "does_not_exist.json")
    ok, detail = dsg._check_profile_json_is_well_formed()
    assert ok is False
    assert "見つかりません" in detail


def test_profile_json_check_detects_malformed_json(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", bad)
    ok, detail = dsg._check_profile_json_is_well_formed()
    assert ok is False
    assert "構文" in detail


def test_profile_json_check_detects_default_action_regression(tmp_path, monkeypatch):
    """[核心・自己レッドチームの固定] defaultActionがSCMP_ACT_ALLOW
    (denylist方式)から変わってしまった場合、正しく検知することを
    確認する。"""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ERRNO",
        "syscalls": [{"names": sorted(dsg._REQUIRED_CORE_DENYLIST), "action": "SCMP_ACT_ERRNO"}],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", bad)
    ok, detail = dsg._check_profile_json_is_well_formed()
    assert ok is False
    assert "SCMP_ACT_ALLOW" in detail


def test_profile_json_check_detects_core_denylist_regression(tmp_path, monkeypatch):
    """[核心・自己レッドチームの固定] §CGで塞いだはずの核心的なシステム
    コール(例: fork, mount)がdenylistから脱落した場合、正しく
    検知することを確認する。"""
    bad = tmp_path / "bad.json"
    weakened = sorted(dsg._REQUIRED_CORE_DENYLIST - {"fork", "mount"})
    bad.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{"names": weakened, "action": "SCMP_ACT_ERRNO"}],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", bad)
    ok, detail = dsg._check_profile_json_is_well_formed()
    assert ok is False
    assert "fork" in detail and "mount" in detail


def test_profile_json_check_detects_execve_reintroduced_into_denylist(tmp_path, monkeypatch):
    """[核心・§CIの回帰防止] §CIで自己発見・自己訂正した退行(execveを
    denylistに含めると、Docker/runcがコンテナのPID1へこのフィルタを
    ロードした直後にENTRYPOINTをexecveする際、コンテナ自体が一度も
    起動できなくなっていた、GRIMOIRE.md §CI参照)が、将来再びdenylist
    へexecveが追加された場合に正しく検知されることを確認する。"""
    bad = tmp_path / "bad.json"
    reintroduced = sorted(dsg._REQUIRED_CORE_DENYLIST | {"execve", "execveat"})
    bad.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{"names": reintroduced, "action": "SCMP_ACT_ERRNO"}],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", bad)
    ok, detail = dsg._check_profile_json_is_well_formed()
    assert ok is False
    assert "execve" in detail


def test_profile_json_check_detects_io_uring_denylist_regression(tmp_path, monkeypatch):
    """[核心・§CLの回帰防止] io_uring_setupがdenylistから脱落した場合に
    正しく検知されることを確認する。io_uringはseccompによる個々の
    syscall監視そのものを構造的に迂回しうる経路(リングバッファへの
    I/O提出は、対応するsyscall自体を呼ばない)であり、Docker 25.0が
    自身の既定allowlistからこれらを除外したのと同じ理由で、本件を
    §CGの核心的な拒否対象群と同様に扱う。GRIMOIRE.md §CL参照。"""
    bad = tmp_path / "bad.json"
    weakened = sorted(dsg._REQUIRED_CORE_DENYLIST - {"io_uring_setup"})
    bad.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{"names": weakened, "action": "SCMP_ACT_ERRNO"}],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", bad)
    ok, detail = dsg._check_profile_json_is_well_formed()
    assert ok is False
    assert "io_uring_setup" in detail


def test_docker_run_reference_check_detects_missing_security_opt(tmp_path, monkeypatch):
    fake_root = tmp_path
    (fake_root / "src").mkdir()
    (fake_root / "src" / "sandalphon_jail.py").write_text(
        'run_cmd = ["docker", "run", "--rm", "--cap-drop=ALL"]\n', encoding="utf-8",
    )
    monkeypatch.setattr(dsg, "ROOT", fake_root)
    ok, detail = dsg._check_docker_run_references_profile()
    assert ok is False
    assert "seccomp" in detail


def test_raw_kernel_enforcement_detects_a_denylist_that_does_not_actually_block(tmp_path, monkeypatch):
    """[核心・自己レッドチームの固定] プロファイルのdenylistに存在しない
    架空の(あるいは誤字で無効な)システムコール名だけを与えた場合でも、
    本物の危険なシステムコール(fork等)は遮断されず、本検査が正しく
    FAILを報告することを確認する。"""
    harmless_profile = tmp_path / "harmless.json"
    harmless_profile.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{"names": ["ustat"], "action": "SCMP_ACT_ERRNO"}],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", harmless_profile)
    status, detail = dsg._check_raw_kernel_enforcement()
    assert status == "FAIL", detail
    assert "fork" in detail or "socket" in detail or "new_process_via_subprocess" in detail or "ptrace" in detail or "mount" in detail


def test_raw_kernel_enforcement_detects_io_uring_setup_not_blocked(tmp_path, monkeypatch):
    """[核心・§CLの固定] fork/socket/ptrace/mountは拒否しているが
    io_uring_setupだけが脱落しているプロファイルを実機のカーネルへ
    ロードした場合、本検査が実際にio_uring_setupが遮断されていない
    ことを(他の本物の危険なシステムコールが正しく遮断されている
    状態でも)正しく検知することを確認する。"""
    missing_io_uring = tmp_path / "missing_io_uring.json"
    missing_io_uring.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{
            "names": sorted(dsg._REQUIRED_CORE_DENYLIST - {"io_uring_setup"}),
            "action": "SCMP_ACT_ERRNO",
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", missing_io_uring)
    status, detail = dsg._check_raw_kernel_enforcement()
    assert status == "FAIL", detail
    assert "io_uring_setup" in detail


def test_raw_kernel_enforcement_detects_docker_default_profile_gaps_not_blocked(tmp_path, monkeypatch):
    """[核心・§CLの固定・2回目] Dockerの既定seccompプロファイルを調査して
    追加で見つけた3件(open_by_handle_at・quotactl・get_mempolicy)が
    denylistから脱落している場合、他の本物の危険なシステムコールが
    正しく遮断されている状態でも、本検査が正しく検知することを確認
    する。"""
    missing = tmp_path / "missing_docker_default_gaps.json"
    weakened = sorted(
        dsg._REQUIRED_CORE_DENYLIST
        | {"io_uring_setup", "io_uring_enter", "io_uring_register"}
    )
    missing.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{"names": weakened, "action": "SCMP_ACT_ERRNO"}],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", missing)
    status, detail = dsg._check_raw_kernel_enforcement()
    assert status == "FAIL", detail
    assert "quotactl" in detail or "open_by_handle_at" in detail or "get_mempolicy" in detail


def test_raw_kernel_enforcement_is_inconclusive_when_libseccomp_missing(monkeypatch):
    import ctypes

    def _boom(name, *a, **kw):
        raise OSError("テスト: libseccomp.so.2が見つからない")

    monkeypatch.setattr(ctypes, "CDLL", _boom)
    status, detail = dsg._check_raw_kernel_enforcement()
    assert status == "INCONCLUSIVE"
    assert "libseccomp" in detail


def test_execve_self_check_passes_on_real_repository():
    """[核心・§CIの直接再現防止] §CIで実機(GitHub Actions)上で初めて
    発見した回帰――本物の`seccomp-profile.json`をロードした直後、まさに
    そのプロセス自身がexecveで自己置換すること(Docker/runcがコンテナの
    PID1にENTRYPOINTを起動させる状況そのもの)が、この実機でも壊れて
    いないことを直接確認する。"""
    status, detail = dsg._check_execve_after_filter_load_still_works()
    assert status in ("PASS", "INCONCLUSIVE"), detail


def test_execve_self_check_detects_the_original_ci_regression_directly(tmp_path, monkeypatch):
    """[核心・§CIの回帰を再現して固定] §CGが元々denylistに含めていた
    execve/execveatを実際に復元したプロファイルを与え、本検査が
    §CIで実機にて発生したのと全く同じ「execveによる自己置換の失敗」を
    正しくFAILとして検知することを確認する(自己レッドチーム)。"""
    reverted = tmp_path / "reverted_to_cg.json"
    reverted.write_text(json.dumps({
        "defaultAction": "SCMP_ACT_ALLOW",
        "syscalls": [{
            "names": ["fork", "vfork", "clone", "clone3", "execve", "execveat"],
            "action": "SCMP_ACT_ERRNO",
            "errnoRet": 1,
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(dsg, "_PROFILE_PATH", reverted)
    status, detail = dsg._check_execve_after_filter_load_still_works()
    assert status == "FAIL", detail


def test_execve_self_check_is_inconclusive_when_libseccomp_missing(monkeypatch):
    import ctypes

    def _boom(name, *a, **kw):
        raise OSError("テスト: libseccomp.so.2が見つからない")

    monkeypatch.setattr(ctypes, "CDLL", _boom)
    status, detail = dsg._check_execve_after_filter_load_still_works()
    assert status == "INCONCLUSIVE"
    assert "libseccomp" in detail


def test_main_reports_pass_or_inconclusive_on_real_repository():
    """[実機の裏付け] このクラウドサンドボックス環境でmain()を実際に
    呼び出し、静的検証・生カーネル検証はPASSし、Dockerコンテナ内での
    最終段のみがINCONCLUSIVE(PASSへの偽装なし)として、例外なく正常
    終了することを確認する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        dsg.main()
    output = buf.getvalue()
    assert "❌" not in output
    assert "✅" in output or "❓" in output


def test_main_reports_fail_when_profile_check_fails(monkeypatch):
    monkeypatch.setattr(dsg, "_check_profile_json_is_well_formed", lambda: (False, "模擬: プロファイルが崩れている"))
    try:
        dsg.main()
        assert False, "プロファイル検証の失敗がFAILとして報告されなかった"
    except SystemExit as e:
        assert e.code == 1


def test_main_reports_fail_when_raw_kernel_check_fails(monkeypatch):
    monkeypatch.setattr(dsg, "_check_raw_kernel_enforcement", lambda: ("FAIL", "模擬: 実際には遮断されなかった"))
    try:
        dsg.main()
        assert False, "生カーネル検証の失敗がFAILとして報告されなかった"
    except SystemExit as e:
        assert e.code == 1
