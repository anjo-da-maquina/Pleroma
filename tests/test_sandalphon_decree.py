"""
tests/test_sandalphon_decree.py
=====================================
[新設 2026-11] angels/sandalphon_decree.py の単体テスト。

本天使(「サンダルフォンの勅令」)は、「Docker/OSレベルの強制サンド
ボックス化」が、静的検閲のみの張りぼてに戻されていないかを、
`src/aegis_system.py`・`src/sandalphon_jail.py`・
`src/ollama_agent_loop.py`の内容を直接文字列検査することで静的に
検証する(§BCで新設)。天使群のテストカバレッジの棚卸しの過程で、
専用テストが一件も存在しないことが判明した。本天使が検査する項目は
いずれも本リポジトリのゼロトラスト設計の中核(Dockerフェイルクローズド・
タイムアウト検知・実運用ループの経路統合)であるため、他の候補より
優先して対応する。

`main()`は`ROOT / "src" / <ファイル名>`という固定パスを直接読むため、
`sandalphon_decree.ROOT`を一時ディレクトリへmonkeypatchし、そこに
各検査項目を満たす/満たさないフィクスチャファイルを置いて検証する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import sandalphon_decree as sdc

VALID_AEGIS_TEXT = (
    "class AegisSystem:\n"
    "    def __init__(self, require_docker_sandbox: bool = True):\n"
    "        pass\n"
    "    def execute(self):\n"
    "        run_in_sandalphon(...)\n"
    "        if not docker_available:\n"
    "            raise PermissionError('docker unavailable')\n"
    "        if timed_out:\n"
    "            raise TimeoutError()\n"
)

VALID_SANDALPHON_TEXT = (
    "def check_docker_available():\n"
    "    subprocess.run(['docker', 'info'])\n"
)

VALID_OLLAMA_LOOP_TEXT = (
    "from src.aegis_system import AegisSystem\n"
    "AegisSystem().execute_ai_intent(code)\n"
)


def _write_fixtures(root, aegis_text=VALID_AEGIS_TEXT, sandalphon_text=VALID_SANDALPHON_TEXT,
                     ollama_text=VALID_OLLAMA_LOOP_TEXT, include_ollama_loop=True):
    src_dir = root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "aegis_system.py").write_text(aegis_text, encoding="utf-8")
    (src_dir / "sandalphon_jail.py").write_text(sandalphon_text, encoding="utf-8")
    if include_ollama_loop:
        (src_dir / "ollama_agent_loop.py").write_text(ollama_text, encoding="utf-8")


def _expect_fail(monkeypatch, root):
    monkeypatch.setattr(sdc, "ROOT", root)
    try:
        sdc.main()
        assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
    except SystemExit as e:
        assert e.code == 1


def test_real_repository_passes():
    """[実機の裏付け] 現時点のリポジトリでは、Docker強制サンドボックス
    化が正しく実運用ループに統合されているため、本天使はPASSを報告
    する。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        sdc.main()
    assert "✅ PASS" in buf.getvalue()


def test_fails_when_required_file_is_missing(monkeypatch, tmp_path):
    """`aegis_system.py`・`sandalphon_jail.py`のいずれかが存在しない
    場合、正しくFAILする。"""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "aegis_system.py").write_text(VALID_AEGIS_TEXT, encoding="utf-8")
    # sandalphon_jail.pyを意図的に作らない
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_docker_sandbox_flag_is_absent(monkeypatch, tmp_path):
    """[核心] `require_docker_sandbox`というフラグ自体が無い場合、
    正しくFAILする。"""
    _write_fixtures(tmp_path, aegis_text=VALID_AEGIS_TEXT.replace("require_docker_sandbox", "something_else"))
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_default_is_not_true(monkeypatch, tmp_path):
    """[核心・フェイルオープン検知] `require_docker_sandbox`の既定値が
    `True`になっていない場合、正しくFAILする(§BCの核心の退行防止)。"""
    bad_text = VALID_AEGIS_TEXT.replace(
        "require_docker_sandbox: bool = True", "require_docker_sandbox: bool = False"
    )
    _write_fixtures(tmp_path, aegis_text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_run_in_sandalphon_is_not_called(monkeypatch, tmp_path):
    """[核心] `run_in_sandalphon`の呼び出しが無い(静的検閲のみの張り
    ぼて)場合、正しくFAILする。"""
    _write_fixtures(tmp_path, aegis_text=VALID_AEGIS_TEXT.replace("run_in_sandalphon", "something_else"))
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_fail_closed_implementation_is_missing(monkeypatch, tmp_path):
    """[核心] Dockerデーモン不在時のフェイルクローズド実装
    (`docker_available`・`PermissionError`)が見つからない場合、正しく
    FAILする。"""
    bad_text = VALID_AEGIS_TEXT.replace("PermissionError", "SomeOtherError")
    _write_fixtures(tmp_path, aegis_text=bad_text)
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_timeout_handling_is_missing(monkeypatch, tmp_path):
    """[核心] タイムアウト検知(`timed_out`)の実装が見つからない場合、
    正しくFAILする。"""
    _write_fixtures(tmp_path, aegis_text=VALID_AEGIS_TEXT.replace("timed_out", "something_else"))
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_sandalphon_daemon_check_is_missing(monkeypatch, tmp_path):
    """[核心] `sandalphon_jail.py`が実際のDockerデーモン接続確認
    (`docker info`相当)を行っていない場合、正しくFAILする(CLIバイナリ
    の存在確認だけでは偽陽性になるため)。"""
    _write_fixtures(
        tmp_path,
        sandalphon_text=VALID_SANDALPHON_TEXT.replace("docker info", "docker --version")
        .replace("check_docker_available", "something_else"),
    )
    _expect_fail(monkeypatch, tmp_path)


def test_fails_when_ollama_loop_does_not_use_aegis_system(monkeypatch, tmp_path):
    """[核心] 唯一の実運用ループ(`ollama_agent_loop.py`)が実際に
    `AegisSystem`経由で検証していない場合、正しくFAILする。"""
    _write_fixtures(tmp_path, ollama_text="def run(code):\n    exec(code)\n")
    _expect_fail(monkeypatch, tmp_path)


def test_passes_when_ollama_loop_file_is_absent(monkeypatch, tmp_path):
    """`ollama_agent_loop.py`自体が存在しない場合は、チェックCがスキップ
    され、他の全条件を満たしていれば正しくPASSする(本天使の意図的な
    設計: ファイルが存在する場合のみBの検査対象とする)。"""
    import io
    from contextlib import redirect_stdout

    _write_fixtures(tmp_path, include_ollama_loop=False)
    monkeypatch.setattr(sdc, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        sdc.main()
    assert "✅ PASS" in buf.getvalue()


def test_passes_with_all_valid_fixtures(monkeypatch, tmp_path):
    """全ての条件を満たす最小構成のフィクスチャでは、想定どおりPASS
    する(回帰防止のための明示的な固定)。"""
    import io
    from contextlib import redirect_stdout

    _write_fixtures(tmp_path)
    monkeypatch.setattr(sdc, "ROOT", tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        sdc.main()
    assert "✅ PASS" in buf.getvalue()
