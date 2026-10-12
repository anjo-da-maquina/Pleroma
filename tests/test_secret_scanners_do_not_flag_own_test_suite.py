"""
[脆弱性修正 2026-10 §BD] 「秘密情報漏洩スキャナが、自分自身のテストスイート
を誤検知する」バグの回帰テスト。

`angels/gabriel_canary.py`(実体は`angels/_common.py`の
`scan_for_leaked_secrets()`)と`angels/firmament_enclave_tee.py`
(`scan_for_hardcoded_sensitive_env_keys()`)は、いずれもリポジトリ全体を
実際にスキャンして、本物の秘密情報が紛れ込んでいないかを検証するCI必須
ステップである。しかし、これらを検証する`tests/test_scan_for_leaked_secrets.py`・
`tests/test_firmament_enclave_tee.py`自身が、意図的に「本物らしい偽の秘密
情報」(例: AWSアクセスキーの形式に一致する文字列、"OPENAI_API_KEY"という
キー名の文字列)をテストフィクスチャとして含んでいたため、CI上で本検査
自身がこれらのテストファイルを「本物の漏洩」と誤検知し続けていた。

実機で確認した通り、これは2026-10-10 23:29のマージ以降、
`.github/workflows/anjo_da_maquina_protocol.yml`(Angels CI)を継続的に
失敗させ続けていた、現在進行中の実害のある不具合だった(GitHub Actionsの
実行履歴で確認済み)。本テストは、このクラスの不具合全体(個別のテスト
ファイル名ではなく「実リポジトリに対して両スキャナを実際に実行した結果が
空であること」)を固定し、将来誰かが別の秘密スキャナ用テストフィクスチャ
を追加した際にも機械的に検知できるようにする。
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "angels"))

from _common import scan_for_leaked_secrets  # noqa: E402
from firmament_enclave_tee import scan_for_hardcoded_sensitive_env_keys  # noqa: E402


def test_scan_for_leaked_secrets_finds_nothing_in_the_real_repository():
    """[修正の核心] angels/gabriel_canary.pyが実際に使う
    scan_for_leaked_secrets()を、rootを指定せず(=実リポジトリ全体に対して)
    呼び出しても、何も検知してはならない。テストフィクスチャ自身が
    誤検知される場合、ここで失敗する。"""
    hits = scan_for_leaked_secrets()
    assert hits == [], (
        f"実リポジトリに対する秘密情報スキャンが、何らかのファイルを誤検知"
        f"している可能性がある(テストフィクスチャ自身の誤検知を含む): {hits}"
    )


def test_scan_for_hardcoded_sensitive_env_keys_finds_nothing_in_the_real_repository():
    """[修正の核心] angels/firmament_enclave_tee.pyが実際に使う
    scan_for_hardcoded_sensitive_env_keys()を、root/self_pathを指定せず
    (=実リポジトリ全体に対して)呼び出しても、何も検知してはならない。"""
    hits = scan_for_hardcoded_sensitive_env_keys()
    assert hits == [], (
        f"実リポジトリに対する環境変数ハードコードスキャンが、何らかの"
        f"ファイルを誤検知している可能性がある(テストフィクスチャ自身の"
        f"誤検知を含む): {hits}"
    )
