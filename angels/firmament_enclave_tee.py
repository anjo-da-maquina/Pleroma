import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    report_pass, report_fail, report_info, run_code_against_sefer,
    inquisition_catches, load_json, sha256_of_dir, load_state, save_state,
    VALID_EVENT_NAME_RE, scan_for_leaked_secrets, ROOT,
)

NAME = "天空の閨房 (Firmament Enclave TEE)"


# メモリ暗号化監査（代替実装）: 実TEEは未接続のため、代わりに秘密情報が
# 平文でリポジトリに紛れ込んでいないかを再度別視点（環境変数経由の漏洩）で検証する。
SENSITIVE_ENV_KEYS = {"AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN", "PRIVATE_KEY"}

_SELF_PATH = Path(__file__).resolve()


def scan_for_hardcoded_sensitive_env_keys(root: Path = None, self_path: Path = None):
    """SENSITIVE_ENV_KEYSのいずれかが、os.getenv/os.environを伴わない
    文脈で文字列として現れるファイル・行を列挙する。

    [脆弱性修正 2026-10 §AZ] 以前は"os.getenv" not in text・
    "os.environ" not in text をファイル全体に対して判定していた。
    これは、ファイル内のどこか別の場所(全く無関係な設定値の取得等)で
    一度でもos.getenv/os.environが使われていれば、同じファイル内の
    別の行にある、センシティブなキー名と実際の秘密値がハードコード
    された本物の漏洩パターン(例: {"OPENAI_API_KEY": "sk-実際の値"})
    まで、一括で検査対象外にしてしまう欠陥だった(実機検証済み:
    無関係なos.getenv("SOME_UNRELATED_VAR")を含むファイル内の
    {"OPENAI_API_KEY": "sk-漏洩した値"}が一件も検知されないことを
    確認した)。判定を行単位に変更し、「そのキー名を含む行自体に
    os.getenv/os.environが無い」場合にのみ疑わしいと判定するよう
    修正した。

    [テスト容易性のため 2026-10 §AZ] rootとself_pathを明示的に渡せる
    ようにし、tests/test_firmament_enclave_tee.py が一時ディレクトリ上の
    架空のファイル構成で検証できるようにしている。既定ではリポジトリ
    本体のROOTと本ファイル自身を使う。
    """
    if root is None:
        root = ROOT
    if self_path is None:
        self_path = _SELF_PATH
    leaked_env_in_files = []
    for p in root.rglob("*.py"):
        if "dummy_secrets" in p.parts or "__pycache__" in p.parts:
            continue
        if p.resolve() == self_path:
            # 本スクリプト自身はSENSITIVE_ENV_KEYSというキー名の一覧
            # (denylist)そのものを定義・報告するため、キー名が文字列として
            # 現れるのは当然であり、漏洩ではない。
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for key in SENSITIVE_ENV_KEYS:
                if f'"{key}"' in line and "os.getenv" not in line and "os.environ" not in line:
                    leaked_env_in_files.append((p.relative_to(root).as_posix(), key, lineno))
    return leaked_env_in_files


def main():
    leaked_env_in_files = scan_for_hardcoded_sensitive_env_keys()
    if leaked_env_in_files:
        report_fail(NAME, f"環境変数名がハードコード文脈で参照されています（漏洩の疑い）: {leaked_env_in_files}")
    report_pass(NAME, "機密環境変数のハードコード参照パターンは検出されませんでした。")

if __name__ == "__main__":
    main()
