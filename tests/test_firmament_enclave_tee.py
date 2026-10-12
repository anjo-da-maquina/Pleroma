"""
[脆弱性修正 2026-10 §AZ] angels/firmament_enclave_tee.py の回帰テスト。

このスクリプトは、センシティブな環境変数名(例: "OPENAI_API_KEY")が、
os.getenv/os.environ経由で安全に読み取られる文脈ではなく、ハードコード
された文脈(漏洩の疑い)で使われていないかをCI上で検査する。

精査の結果、修正前は"os.getenv" not in text等の判定をファイル全体に
対して行っており、ファイル内のどこか別の場所(全く無関係な設定値の取得等)
で一度でもos.getenv/os.environが使われていれば、同じファイル内の別の行に
ある本物の漏洩パターン(例: `{"OPENAI_API_KEY": "sk-実際の値"}`)まで、
一括で検査対象外にしてしまう欠陥があった。本テストは、この種の「無関係な
getenv呼び出しが同じファイル内の本物の漏洩を隠してしまう」ケースを実機で
固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
from firmament_enclave_tee import scan_for_hardcoded_sensitive_env_keys


def test_detects_leak_even_when_file_also_contains_an_unrelated_getenv_call(tmp_path):
    """[脆弱性の核心] 同じファイル内に無関係なos.getenv呼び出しがあっても、
    別の行にあるハードコードされた秘密は検知されなければならない。"""
    leaky_file = tmp_path / "leaky_config.py"
    leaky_file.write_text(
        "import os\n"
        "\n"
        "# この行には実際のハードコードされた秘密がある(本物の漏洩のつもり)\n"
        'DEFAULT_CONFIG = {"OPENAI_API_KEY": "sk-THIS_IS_A_REAL_LEAKED_SECRET"}\n'
        "\n"
        "def get_other_setting():\n"
        "    # この無関係なos.getenv呼び出しが、修正前はファイル全体の検査を\n"
        "    # 無効化してしまっていた\n"
        '    return os.getenv("SOME_UNRELATED_VAR")\n',
        encoding="utf-8",
    )
    hits = scan_for_hardcoded_sensitive_env_keys(root=tmp_path, self_path=Path("/nonexistent"))
    assert any(h[1] == "OPENAI_API_KEY" for h in hits), (
        f"同一ファイル内の無関係なos.getenv呼び出しが、本物の漏洩の検知を妨げている: {hits}"
    )


def test_does_not_flag_a_legitimate_getenv_call_on_the_same_line(tmp_path):
    """[回帰防止] os.getenv("OPENAI_API_KEY")のような、キー名と
    os.getenvが同じ行にある正規の読み取りは誤検知してはならない。"""
    safe_file = tmp_path / "safe_config.py"
    safe_file.write_text(
        "import os\n"
        'api_key = os.getenv("OPENAI_API_KEY")\n',
        encoding="utf-8",
    )
    hits = scan_for_hardcoded_sensitive_env_keys(root=tmp_path, self_path=Path("/nonexistent"))
    assert hits == [], f"正規のos.getenv呼び出しを誤って漏洩と判定した: {hits}"


def test_does_not_flag_its_own_source_file():
    """[回帰防止] 本スクリプト自身はSENSITIVE_ENV_KEYSという denylist を
    定義・報告するためにキー名を文字列として含むが、これは漏洩ではない。"""
    hits = scan_for_hardcoded_sensitive_env_keys()
    own_file_hits = [h for h in hits if h[0] == "firmament_enclave_tee.py"]
    assert own_file_hits == [], f"スクリプト自身のdenylist定義を誤検知した: {own_file_hits}"
