import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "guard_docker_sandbox_enforcement_decay - 思考統制監査: 「Docker/OSレベルの強制サンドボックス化」が、静的検閲(1〜3層) を素通しするだけの張りぼてに戻されていないかを静的に検証する。"


# 思考統制監査: 「Docker/OSレベルの強制サンドボックス化」が、静的検閲(1〜3層)
# を素通しするだけの張りぼてに戻されていないかを静的に検証する。
# 具体的には以下の2点を確認する:
#   A. aegis_system.py が既定で Sandalphon(Docker隔離結界)での動的実行検証を
#      強制しており(require_docker_sandbox の既定値がTrue)、かつ
#      Dockerデーモン不在時にフェイルクローズド(拒否)していること。
#   B. 唯一の実運用エージェントループ(ollama_agent_loop.py)が、実際に
#      AegisSystem(Gabriel+Sandalphon込み)を経由していること。
def main():
    aegis_path = ROOT / "src" / "aegis_system.py"
    sandalphon_path = ROOT / "src" / "sandalphon_jail.py"
    ollama_loop_path = ROOT / "src" / "ollama_agent_loop.py"

    for p in (aegis_path, sandalphon_path):
        if not p.exists():
            report_fail(NAME, f"必須ファイルが見つかりません: {p}")
            return

    aegis_text = aegis_path.read_text(encoding="utf-8-sig")
    sandalphon_text = sandalphon_path.read_text(encoding="utf-8-sig")

    # A-1: 既定でフェイルクローズド（require_docker_sandbox: bool = True）
    if "require_docker_sandbox" not in aegis_text:
        report_fail(NAME, "AegisSystemにDocker強制フラグ(require_docker_sandbox)が存在しません。")
    if "require_docker_sandbox: bool = True" not in aegis_text and "require_docker_sandbox=True" not in aegis_text:
        report_fail(NAME, "require_docker_sandboxの既定値がTrue(強制)になっていません。フェイルオープンな設定は認められません。")

    # A-2: 実際にSandalphonの動的実行結果を見て拒否しているか
    if "run_in_sandalphon" not in aegis_text:
        report_fail(NAME, "AegisSystemがSandalphon(run_in_sandalphon)を呼び出していません。静的検閲のみの張りぼてに戻っています。")
    if "docker_available" not in aegis_text or "PermissionError" not in aegis_text:
        report_fail(NAME, "Dockerデーモン不在時にPermissionErrorでフェイルクローズドする実装が見つかりません。")
    if "timed_out" not in aegis_text:
        report_fail(NAME, "Sandalphonのタイムアウト(無限ループ等の遅延攻撃)を検知して拒否する実装が見つかりません。")

    # B: sandalphon_jail.py が「デーモンへの実際の接続確認」をしているか
    #    (docker --version だけではCLIバイナリの存在しか確認できず、
    #     デーモン未起動でも偽陽性で通過してしまうため)
    if "docker info" not in sandalphon_text and "check_docker_available" not in sandalphon_text:
        report_fail(NAME, "sandalphon_jail.pyがDockerデーモンへの実際の接続確認(docker info相当)を行っていません。")

    # C: 唯一の実運用ループが実際にAegisSystemを経由しているか
    if ollama_loop_path.exists():
        loop_text = ollama_loop_path.read_text(encoding="utf-8-sig")
        if "AegisSystem" not in loop_text or "execute_ai_intent" not in loop_text:
            report_fail(NAME, "ollama_agent_loop.py(唯一の実運用ループ)がAegisSystem経由のGabriel/Sandalphon検証を経由していません。")

    report_pass(NAME, "Docker/OSレベルの強制サンドボックス化が、フェイルクローズドな設計のまま実運用ループに正しく統合されています。")

if __name__ == "__main__":
    main()
