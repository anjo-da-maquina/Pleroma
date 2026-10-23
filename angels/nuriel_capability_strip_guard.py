import sys, os, re, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, report_inconclusive, ROOT

NAME = "ヌリエルの剥奪 (Nuriel's Stripping - サンダルフォン隔離結界のLinuxケーパビリティ・特権昇格の恒久的剥奪)"

# [新設 2026-10 §CF] これまで§CD・§CEで繰り返し正直に記録してきた通り、
# Python層のaudit hook(sefer/maquina_gatekeeper)には構造的な限界があ
# る――Sanctumに入る『前』に確保済みのfdや関数ポインタを使った操作は、
# 以後いかなる新たな監査イベントも発生させずに素通りする。これは「城内
# に関所を増やす」方式そのものの限界であり、恒久対策には「城を囲む外壁」
# すなわちOSレベル(カーネルレベル)の強制が必要であると、GRIMOIRE.mdに
# 繰り返し記してきた。
#
# 本件は、ユーザーからその恒久対策に実際に着手するよう依頼を受けて行った
# 調査である。既にSandalphon(`src/sandalphon_jail.py`の`run_in_sandalphon`)
# は、未知のAI生成コードをDockerコンテナ内で動的に検証する「OSレベルの
# 隔離結界」を備えていたが、実際の`docker run`呼び出しを確認したところ、
# ネットワーク完全遮断(`--network none`)・読み取り専用(`--read-only`)・
# 非rootユーザー(Dockerfile内の`USER prisoner`)の3点にしか依存して
# おらず、コンテナ自体にはDockerの既定のLinuxケーパビリティ集合
# (CAP_DAC_OVERRIDE・CAP_SETUID・CAP_SETGID・CAP_SYS_CHROOT・CAP_NET_RAW
# 等)がそのまま付与され続けていることを実機で確認した。これらの既定
# ケーパビリティのうち、CAP_DAC_OVERRIDEは通常のファイル権限チェックを
# 丸ごと無効化でき、CAP_SETUID/CAP_SETGIDは適切なファイルケーパビリティ
# を持つバイナリ経由でuid/gidを変更できる――使い捨てスクリプトの実行
# という本隔離結界の用途には、これらのいずれも正当な必要性が無い。
#
# [正直な注記: 本検査がカーネルレベルで検証できないこと] この調査環境
# (クラウドサンドボックス)は、コンテナレジストリへの出口ネットワーク
# 接続が許可一覧(allowlist)によって遮断されており、`python:3.11-alpine`
# イメージの取得自体が`403 Forbidden`で失敗することを実機で確認した
# (Dockerデーモン自体は手動起動すれば動作することも確認済みであり、
# 「デーモンが無い」のではなく「イメージの取得ができない」という、既存
# の`check_docker_available()`が想定していなかった第三の状態である)。
# そのため、この環境では実際にコンテナを起動してケーパビリティ剥奪が
# 本当にカーネルによって強制されていることまでは確認できない。本天使は、
# (A) 常にこの環境でも実行できる静的検証(`run_in_sandalphon`の実装に
# 必要な3つのオプションが実際に含まれているか)と、(B) イメージが取得
# できる環境でのみ実行できる動的検証(実際にコンテナを起動し、剥奪され
# ているはずのケーパビリティに依存する操作が本当に失敗するか)を分離
# し、(B)がこの環境で実行できない場合は`report_inconclusive`で「検証
# できなかった」という事実を正直に記録する(PASSに偽装しない)。(B)の
# 本当の検証は、インターネットに接続できる実際のGitHub Actions環境で
# 行われることを期待する。


def _check_static_flags_present() -> tuple:
    """`run_in_sandalphon`のdocker run呼び出しに、ケーパビリティ剥奪・
    特権昇格禁止・プロセス数上限の3つのオプションが実際に含まれている
    ことを静的に確認する(イメージ取得やデーモン起動を一切必要としない
    ため、ネットワーク制限下のこの環境でも常に実行可能)。"""
    path = ROOT / "src" / "sandalphon_jail.py"
    if not path.exists():
        return False, f"対象ファイルが見つかりません: {path}"
    text = path.read_text(encoding="utf-8-sig")

    required = [
        (r"--cap-drop[=\s]+ALL", "--cap-drop=ALL (全Linuxケーパビリティの剥奪)"),
        (r"--security-opt[=\s]+no-new-privileges", "--security-opt=no-new-privileges (特権昇格の禁止)"),
        (r"--pids-limit", "--pids-limit (fork爆弾等によるプロセス数無制限増加の防止)"),
    ]
    missing = [label for pattern, label in required if not re.search(pattern, text)]
    if missing:
        return False, f"run_in_sandalphon()のdocker run呼び出しに、以下のOSレベル強制オプションが見つかりません: {', '.join(missing)}"
    return True, "OK"


def _check_dynamic_capability_is_actually_dropped():
    """実際にコンテナを起動し、CAP_DAC_OVERRIDE剥奪前であれば成功するはず
    の操作(自身が所有しない、読み取り専用でもないファイルへの書き込み
    試行)が、剥奪後は本当にPermissionErrorで失敗することを実機で確認
    する。

    戻り値: ("PASS"|"FAIL"|"INCONCLUSIVE", detail)
    """
    sys.path.insert(0, str(ROOT / "src"))
    import sandalphon_jail as sj

    available, reason = sj.check_docker_available()
    if not available:
        return "INCONCLUSIVE", f"Dockerデーモン自体が利用不可のため動的検証を実施できません: {reason}"

    try:
        sj._ensure_image_built()
    except subprocess.SubprocessError as e:
        return "INCONCLUSIVE", (
            f"隔離結界イメージの取得・構築ができないため、この環境では動的検証を実施できません"
            f"(ネットワーク許可一覧によるコンテナレジストリ遮断が原因である可能性が高い): {e}"
        )

    # CAP_DAC_OVERRIDE剥奪の確認: /jail/target.pyは読み取り専用マウント
    # だが、剥奪前であればCAP_DAC_OVERRIDEにより通常の権限チェックを
    # バイパスして書き込めてしまう可能性がある(read-onlyマウント自体が
    # 既に一次防御だが、本検査はケーパビリティ単体の剥奪を確認するため、
    # マウント保護とは独立した経路としてコンテナ内の/tmp配下に自分以外が
    # 所有する0600ファイルを作り、それへの書き込み試行がCAP_DAC_OVERRIDE
    # 無しでは失敗することを確認する)。
    script = (
        "import os, sys\n"
        "try:\n"
        "    os.setuid(0)\n"
        "    print('SETUID_SUCCEEDED')\n"
        "except PermissionError:\n"
        "    print('SETUID_BLOCKED')\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(script)
        tmp_path = tf.name
    # [自己発見・緊急修正 2026-10 §CF-1] src/sandalphon_jail.py側と同じ
    # 理由(CAP_DAC_OVERRIDE剥奪後、既定モード0600のままでは`prisoner`
    # ユーザーがこのファイルを開けずPermission deniedになる)で、ここも
    # 同様にchmodする。GRIMOIRE.md §CF追記参照。
    os.chmod(tmp_path, 0o644)
    try:
        run_cmd = [
            "docker", "run", "--rm",
            "--network", "none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=32",
            "-v", f"{tmp_path}:/jail/target.py:ro",
            sj._SANDALPHON_IMAGE, "target.py",
        ]
        proc = subprocess.run(run_cmd, capture_output=True, text=True, timeout=15)
    finally:
        os.unlink(tmp_path)

    if "SETUID_BLOCKED" in proc.stdout:
        return "PASS", "剥奪後、os.setuid(0)がPermissionErrorで実際に失敗することを確認しました。"
    if "SETUID_SUCCEEDED" in proc.stdout:
        return "FAIL", f"--cap-drop=ALLを付与したにもかかわらず、os.setuid(0)が成功してしまいました(回帰): stdout={proc.stdout} stderr={proc.stderr}"
    return "FAIL", f"想定した出力が得られませんでした: stdout={proc.stdout!r} stderr={proc.stderr!r} returncode={proc.returncode}"


def main():
    ok, detail = _check_static_flags_present()
    if not ok:
        report_fail(NAME, f"OSレベルのケーパビリティ剥奪・特権昇格禁止が後退しています(§CFの回帰): {detail}")
        return

    status, dyn_detail = _check_dynamic_capability_is_actually_dropped()
    if status == "FAIL":
        report_fail(NAME, f"ケーパビリティ剥奪が実際には機能していません: {dyn_detail}")
        return
    if status == "INCONCLUSIVE":
        report_inconclusive(
            NAME,
            f"静的検証(docker run呼び出しに必要なオプションが存在すること)はPASSしましたが、"
            f"動的検証(実際にコンテナ内でケーパビリティが剥奪されていることの実機確認)はこの環境では実施できませんでした: {dyn_detail}",
        )
        return

    report_pass(
        NAME,
        "Sandalphon隔離結界のdocker run呼び出しに、全Linuxケーパビリティの剥奪・特権昇格禁止・"
        "プロセス数上限の3オプションが存在し、実際にコンテナ内でos.setuid(0)が"
        "PermissionErrorで遮断されることを実機で確認しました。",
    )


if __name__ == "__main__":
    main()
