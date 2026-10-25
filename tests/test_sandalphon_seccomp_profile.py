"""
tests/test_sandalphon_seccomp_profile.py
=========================================
[新設 2026-10 §CG] `run_in_sandalphon()`が、実際に
`src/sandalphon/seccomp-profile.json`を`--security-opt=seccomp=`で
docker runへ渡していることの回帰テスト。

§CFで導入したLinuxケーパビリティの剥奪は「root相当の特権の有無」を
制御するが、§CD・§CEで発見した迂回手口(Sanctumに入る前に確保済みの
fd・関数ポインタを使う)は特権を一切必要としない。本修正は、カーネル
レベルでシステムコール自体を直接拒否するseccompプロファイルを
`docker run`へ渡すことで、この隙間を塞ぐ。
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sandalphon_jail as sj


def _captured_run_cmd(monkeypatch):
    monkeypatch.setattr(sj, "check_docker_available", lambda: (True, ""))
    monkeypatch.setattr(sj, "_ensure_image_built", lambda: None)

    captured = []

    def _fake_run(cmd, **kwargs):
        captured.append(cmd)
        class _FakeProc:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    sj.run_in_sandalphon("print('ok')")
    assert captured, "docker runが一度も呼ばれなかった"
    return captured[0]


def test_run_in_sandalphon_passes_the_seccomp_profile(monkeypatch):
    cmd = _captured_run_cmd(monkeypatch)
    seccomp_args = [a for a in cmd if a.startswith("--security-opt=seccomp=")]
    assert seccomp_args, f"docker run呼び出しに--security-opt=seccomp=...が見つかりません: {cmd}"


def test_seccomp_profile_path_in_the_command_actually_exists_on_disk(monkeypatch):
    """[核心] docker runへ渡しているパスが、実際に存在するプロファイル
    ファイルを指していることを確認する(タイプミス等で存在しないパスを
    渡していれば、Dockerはそれを静かに無視するかエラーになるため、
    "引数が付いていればOK"では不十分)。"""
    cmd = _captured_run_cmd(monkeypatch)
    seccomp_args = [a for a in cmd if a.startswith("--security-opt=seccomp=")]
    assert seccomp_args
    profile_path = Path(seccomp_args[0].split("=", 2)[2])
    assert profile_path.exists(), f"docker runが参照するseccompプロファイルが実際には存在しません: {profile_path}"
    assert profile_path.name == "seccomp-profile.json"


def test_run_in_sandalphon_still_keeps_capability_and_privilege_flags(monkeypatch):
    """[誤検知防止・§CFの非退行] seccompプロファイルの追加が、既存の
    §CFのケーパビリティ剥奪・特権昇格禁止オプションを置き換えたり
    消したりしていないことを確認する(多層防御の各層が互いを壊さない
    ことの固定)。"""
    cmd = _captured_run_cmd(monkeypatch)
    assert "--cap-drop=ALL" in cmd
    assert "--security-opt=no-new-privileges" in cmd
    assert "--pids-limit=32" in cmd
