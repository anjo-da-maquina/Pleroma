"""
tests/test_sandalphon_jail_mount_permissions.py
================================================
[新設 2026-10 §CF-1・自己発見した退行の固定] §CFで`run_in_sandalphon()`に
`--cap-drop=ALL`を追加した直後、実際にGitHub Actions上でこの隔離結界を
動的に検証したところ、コンテナ内の`prisoner`ユーザーが
`PermissionError: [Errno 13] Permission denied`で`/jail/target.py`を
開けず、正規の実行まで一律に失敗する退行を実機で発見した。

原因: `tempfile.NamedTemporaryFile`は既定でモード0600(所有者のみ読み
書き可)でファイルを作成する。`--cap-drop=ALL`導入前は、Dockerの既定の
ケーパビリティ集合に含まれる`CAP_DAC_OVERRIDE`(通常のファイル権限
チェックを無視できる特権)により、ホスト側の所有者とは異なるコンテナ内
の`prisoner`ユーザーでもこの0600ファイルを読み取れてしまっていた――
すなわちこのコードは気づかないうちにCAP_DAC_OVERRIDEに依存していた。
これは、GRIMOIRE.md全体で繰り返し記録してきた「見えない依存関係」の
一種であり、セキュリティを強化したつもりの変更が正規の機能そのものを
壊してしまった、素直に認めるべき自己発見の退行である。

対応: マウント前に`os.chmod(tmp_path, 0o644)`で全ユーザー読み取り可能
にすることで、CAP_DAC_OVERRIDEを復活させずに解決した(Docker側の
`:ro`マウントにより書き込みは引き続き一切できない)。本テストはこの
chmod処理自体の回帰を固定する。
"""
import os
import stat
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sandalphon_jail as sj


def test_run_in_sandalphon_makes_the_mounted_script_world_readable(monkeypatch):
    """[核心・自己レッドチームの固定] §CF-1修正前の実装(chmodなし)に
    戻した場合、マウントされるスクリプトファイルがtempfileの既定モード
    (0600、所有者のみ読み取り可)のままになり、コンテナ内の非所有者
    ユーザー(prisoner)が読めなくなることを、実際のファイルモードを
    検査して確認する。"""
    monkeypatch.setattr(sj, "check_docker_available", lambda: (True, ""))
    monkeypatch.setattr(sj, "_ensure_image_built", lambda: None)

    observed_modes = []

    def _fake_run(cmd, **kwargs):
        # cmd の中から `-v host:container:ro` の host側パスを取り出し、
        # その時点でのファイルモードを記録する。
        for i, arg in enumerate(cmd):
            if arg == "-v" and i + 1 < len(cmd):
                host_path = cmd[i + 1].split(":")[0]
                observed_modes.append(stat.S_IMODE(os.stat(host_path).st_mode))
        class _FakeProc:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    sj.run_in_sandalphon("print('ok')")

    assert observed_modes, "docker runコマンドから-vマウント指定が見つからず、検証対象のファイルを特定できなかった"
    for mode in observed_modes:
        # 0600(所有者のみ)ではなく、少なくとも他ユーザーの読み取り
        # ビット(0o004)が立っていることを確認する。
        assert mode & 0o004, (
            f"マウントされるスクリプトファイルが他ユーザー読み取り不可(mode={oct(mode)})のままです。"
            f"--cap-drop=ALL導入後はCAP_DAC_OVERRIDEに頼れないため、コンテナ内のprisonerユーザーが"
            f"このファイルを開けず、正規の実行まで一律に失敗します(実機で発見した退行の再発)。"
        )


def test_run_in_sandalphon_still_does_not_grant_write_to_others(monkeypatch):
    """[誤検知防止] 読み取り可能にする修正が、書き込みビットまで誤って
    付与していないことを確認する(最小権限の原則)。"""
    monkeypatch.setattr(sj, "check_docker_available", lambda: (True, ""))
    monkeypatch.setattr(sj, "_ensure_image_built", lambda: None)

    observed_modes = []

    def _fake_run(cmd, **kwargs):
        for i, arg in enumerate(cmd):
            if arg == "-v" and i + 1 < len(cmd):
                host_path = cmd[i + 1].split(":")[0]
                observed_modes.append(stat.S_IMODE(os.stat(host_path).st_mode))
        class _FakeProc:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    sj.run_in_sandalphon("print('ok')")

    assert observed_modes
    for mode in observed_modes:
        assert not (mode & 0o022), f"グループ/他ユーザーへの書き込みビットが不必要に付与されています(mode={oct(mode)})"
