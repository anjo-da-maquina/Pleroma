import os
import sys
import tempfile
import subprocess
from pathlib import Path

# [2026-10 改修] これまで本モジュールはCLIから手動で呼び出す場合のみ
# 機能する独立ツールであり、AegisSystem/AI実行経路からは一度も呼ばれて
# いなかった（=「Docker隔離は任意・手動のおまけ」でしかなかった）。
# `run_in_sandalphon()` を切り出し、aegis_system.py からの
# 強制的（mandatory）な動的検証に使えるようにする。
_SANDALPHON_IMAGE = "sandalphon-jail"
_SANDALPHON_DOCKERFILE_DIR = Path(__file__).resolve().parent / "sandalphon"
_SANDALPHON_SECCOMP_PROFILE = _SANDALPHON_DOCKERFILE_DIR / "seccomp-profile.json"


def check_docker_available() -> tuple[bool, str]:
    """Dockerエンジン(デーモン込み)が実際に使用可能かを確認する。
    `docker --version` はCLIバイナリの存在しか確認できず、デーモンが
    起動していない環境（Docker Desktop未起動等）でも偽陽性で成功して
    しまうため、`docker info` でデーモンへの接続まで検証する。
    戻り値: (利用可能か, 利用不可の場合の理由)
    """
    try:
        subprocess.run(
            ["docker", "--version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5,
        )
    except FileNotFoundError:
        return False, "Dockerエンジンが検知できません（未インストール）。"
    except subprocess.SubprocessError:
        return False, "Dockerバイナリの呼び出しに失敗しました。"

    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=8,
        )
    except subprocess.CalledProcessError:
        return False, "Dockerデーモンに接続できません（Docker Desktop等が起動していない可能性）。"
    except subprocess.SubprocessError:
        return False, "Dockerデーモンへの接続確認がタイムアウトしました。"

    return True, ""


def _ensure_image_built() -> None:
    try:
        subprocess.run(
            ["docker", "image", "inspect", _SANDALPHON_IMAGE],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["docker", "build", "-t", _SANDALPHON_IMAGE, str(_SANDALPHON_DOCKERFILE_DIR)],
            check=True,
        )


def run_in_sandalphon(code: str, timeout: int = 5) -> dict:
    """渡されたPythonコード文字列を、ネットワーク完全遮断・読み取り専用の
    Dockerコンテナ内で動的に実行し、結果を構造化して返す。

    戻り値のキー:
      docker_available (bool): Dockerデーモンが利用可能だったか
      reason (str):            利用不可だった場合の理由
      executed (bool):         実際に隔離実行まで到達したか
      timed_out (bool):        タイムアウト（無限ループ等の遅延戦術）で強制終了したか
      returncode (int|None):   コンテナ内プロセスの終了コード
      stdout (str), stderr (str)
    """
    result = {
        "docker_available": False, "reason": "", "executed": False,
        "timed_out": False, "returncode": None, "stdout": "", "stderr": "",
    }

    available, reason = check_docker_available()
    result["docker_available"] = available
    result["reason"] = reason
    if not available:
        return result

    try:
        _ensure_image_built()
    except subprocess.SubprocessError as e:
        result["docker_available"] = False
        result["reason"] = f"隔離結界(イメージ)の構築に失敗しました: {e}"
        return result

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(code)
        tmp_path = Path(tf.name)

    # [自己発見・緊急修正 2026-10 §CF-1] `tempfile.NamedTemporaryFile`は
    # 既定でモード0600(所有者のみ読み書き可)でファイルを作成する。
    # これまでコンテナ内の`--cap-drop=ALL`導入前は、Dockerの既定の
    # ケーパビリティ集合に含まれる`CAP_DAC_OVERRIDE`(通常のファイル
    # 権限チェックを無視できる特権)により、ホスト側の所有者(このプロ
    # セスの実行uid)とは異なるコンテナ内の`prisoner`ユーザーでも、この
    # 0600ファイルを読み取れてしまっていた――すなわち、このコードは
    # 気づかないうちにCAP_DAC_OVERRIDEに依存していた。`--cap-drop=ALL`
    # を追加した直後、実際にGitHub Actions上でこの隔離結界を動的に検証
    # したところ、`prisoner`ユーザーが`/jail/target.py`を開けず
    # `PermissionError: [Errno 13] Permission denied`で失敗することを
    # 実機で発見した(GRIMOIRE.md §CF追記参照)。これは正規の実行まで
    # 一律に失敗させてしまう、本修正自身が引き起こした退行である。
    # ケーパビリティに頼らず、通常のUNIXファイル権限だけで「全ユーザー
    # 読み取り可」にすることで、CAP_DAC_OVERRIDEを復活させずに解決する
    # (`:ro`でのbind mountにより書き込みは引き続き一切できない)。
    os.chmod(tmp_path, 0o644)

    try:
        run_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            # [新設 2026-10 §CF] これまでSandalphonの隔離は「ネットワーク
            # 完全遮断・読み取り専用・非rootユーザー」の3点のみに依存して
            # いたが、コンテナ自体にはDockerの既定のLinuxケーパビリティ
            # 集合(CAP_DAC_OVERRIDE・CAP_SETUID・CAP_SETGID・
            # CAP_SYS_CHROOT・CAP_NET_RAW等)がそのまま残っており、万一
            # 隔離結界の内部で任意コード実行を許してしまった場合、
            # これらのケーパビリティを使ってファイル権限チェックの迂回
            # (CAP_DAC_OVERRIDE)やuid/gidの変更(CAP_SETUID/SETGID)が
            # 理論上可能な状態だった。本隔離結界(1回限りの使い捨て
            # スクリプト実行)には、いかなるLinuxケーパビリティも正当な
            # 必要性が無いため、全て剥奪する。また、`no-new-privileges`
            # を付与し、setuid/setgidビットの付いたバイナリやファイル
            # ケーパビリティによる特権昇格を、カーネルレベルで一切
            # 不可能にする。これらはPython層のaudit hook
            # (sefer/maquina_gatekeeper)とは独立した、カーネルが直接
            # 強制するOSレベルの防御であり、Sanctumに入る『前』に
            # 解決済みのfd・関数ポインタを使った既知の迂回手口(§CD・§CE)
            # に対しても、「迂回に成功した後にできる操作」そのものを
            # 狭める効果がある。さらに`pids-limit`で、fork爆弾等による
            # プロセス数の無制限な増加(ホスト側のPIDテーブル枯渇という
            # サービス拒否攻撃)を防ぐ。
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=32",
            # [新設 2026-10 §CG] §CFで取り上げたLinuxケーパビリティは
            # 「root相当の特権の有無」を制御するが、「どのシステムコール
            # 自体を呼べるか」は制御しない――無権限プロセスのままでも
            # fork/clone/execve/ptrace/mount/socket等は、特権を一切使わ
            # ずに呼べてしまう。§CD・§CEで発見した「Sanctumに入る前に
            # 確保済みのfd・関数ポインタを使った迂回」は、まさにこの
            # 「無権限のままでも到達できるシステムコール」の範疇にある。
            # seccompプロファイル(src/sandalphon/seccomp-profile.json)
            # は、カーネルレベルでこれらのシステムコール自体を直接
            # 拒否する、ケーパビリティ剥奪とは独立したもう一枚の壁で
            # ある。プロファイルの設計方針・denylist各項目の根拠は
            # 当該JSONファイル内のcommentフィールドとGRIMOIRE.md §CG
            # に詳述している。
            f"--security-opt=seccomp={_SANDALPHON_SECCOMP_PROFILE}",
            "-v", f"{tmp_path}:/jail/target.py:ro",
            _SANDALPHON_IMAGE, "target.py",
        ]
        try:
            proc = subprocess.run(run_cmd, capture_output=True, text=True, timeout=timeout)
            result["executed"] = True
            result["returncode"] = proc.returncode
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
        except subprocess.TimeoutExpired:
            result["executed"] = True
            result["timed_out"] = True
    finally:
        tmp_path.unlink(missing_ok=True)

    return result


def execute_in_sandalphon(target_file):
    """CLIから `python src/sandalphon_jail.py <file>` として手動実行するための
    従来互換のラッパー。実体は run_in_sandalphon() に委譲する。"""
    print(f"=== [サンダルフォンの絶対隔離結界] '{target_file}' を隔離次元へ転送します ===")
    file_path = Path(target_file).absolute()

    if not file_path.exists():
        print(f"[エラー] 対象ファイルが見つかりません: {target_file}")
        sys.exit(1)

    print("[システム] 隔離結界(Dockerコンテナ)の展開状況を確認中...")
    code = file_path.read_text(encoding="utf-8")
    result = run_in_sandalphon(code)

    if not result["docker_available"]:
        print(f"[致命的エラー] {result['reason']} サンダルフォンを召喚するには、ホストOSでDockerデーモンが起動している必要があります。")
        sys.exit(1)

    print("[サンダルフォン] 結界展開。ネットワーク完全遮断、リードオンリー権限での動的解析を開始。\n")
    print("-" * 50)

    if result["timed_out"]:
        print("\n" + "-" * 50)
        print("=> [結果: 処刑] 実行がタイムアウト(5秒)を超過。無限ループ攻撃等の遅延戦術と断定し、コンテナを物理破壊しました。")
        return

    print(result["stdout"], end="")
    if result["stderr"]:
        print(f"[異常出力]\n{result['stderr']}", end="")
    print("\n" + "-" * 50)
    print(f"=> [結果] 隔離領域での実行が完了しました。(終了コード: {result['returncode']})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用法: python src/sandalphon_jail.py <対象のPythonファイル>")
        sys.exit(1)
    execute_in_sandalphon(sys.argv[1])
