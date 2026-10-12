"""
tests/test_azazel_dependency_audit.py
========================================
angels/azazel_dependency_audit.py の回帰テスト。

本物の pip-audit / PyPI Advisory Database への実際のネットワーク到達性
には依存しない(このテスト自体を含むサンドボックス環境がネットワーク
制限下にある可能性があるため)。subprocess.run をモックし、以下の3つの
分岐が正しく動作することのみを検証する:
  1. pip-auditが利用できない場合、フェイルクローズド(exit code 1)で
     「安全である」と主張しないこと。
  2. pip-auditが既知の脆弱性を検出した場合、exit code 1で詳細を報告する
     こと。
  3. pip-auditが脆弱性ゼロを報告した場合、exit code 0でPASSすること。
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANGELS_DIR = REPO_ROOT / "angels"


def _run_with_stubbed_subprocess(stub_script: str) -> subprocess.CompletedProcess:
    """azazel_dependency_audit.py をサブプロセスとして実行し、その内部の
    subprocess.run呼び出しをstub_scriptで差し替える。"""
    script = f"""
import sys, types
sys.path.insert(0, {str(ANGELS_DIR)!r})

{stub_script}

import subprocess
subprocess.run = _fake_run

import runpy
sys.argv = ["azazel_dependency_audit.py"]
try:
    runpy.run_path({str(ANGELS_DIR / "azazel_dependency_audit.py")!r}, run_name="__main__")
except SystemExit as e:
    sys.exit(e.code or 0)
"""
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_pip_audit_unavailable_fails_closed():
    """[核心] pip-auditが全く利用できない(インストールもできない)場合、
    『調べていないのに安全だと主張する』ことを避け、フェイルクローズドで
    exit code 1になること。"""
    stub = """
def _fake_run(cmd, *a, **kw):
    raise FileNotFoundError("pip_audit not found")
"""
    res = _run_with_stubbed_subprocess(stub)
    assert res.returncode == 1, f"stdout={res.stdout} stderr={res.stderr}"
    assert "FAIL" in res.stdout


def test_known_vulnerability_is_reported_and_fails():
    """[核心] pip-auditが既知の脆弱性を検出した場合、exit code 1で
    詳細(パッケージ名・CVE ID)を報告すること。"""
    stub = """
import json as _json

class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

_call_count = {"n": 0}

def _fake_run(cmd, *a, **kw):
    _call_count["n"] += 1
    if "--version" in cmd:
        return _FakeCompleted(returncode=0, stdout="pip-audit 2.7.0")
    if "pip_audit" in cmd and "-r" in cmd:
        payload = {
            "dependencies": [
                {"name": "requests", "version": "2.32.3", "vulns": [
                    {"id": "PYSEC-2024-XXXX", "fix_versions": ["2.32.4"], "description": "fake"}
                ]},
                {"name": "pytest", "version": "9.1.1", "vulns": []},
            ]
        }
        return _FakeCompleted(returncode=0, stdout=_json.dumps(payload))
    return _FakeCompleted(returncode=0, stdout="")
"""
    res = _run_with_stubbed_subprocess(stub)
    assert res.returncode == 1, f"stdout={res.stdout} stderr={res.stderr}"
    assert "requests" in res.stdout
    assert "PYSEC-2024-XXXX" in res.stdout


def test_duplicate_vuln_ids_from_multiple_data_sources_are_deduplicated_in_report():
    """[実機検証 2026-10] 実際のGitHub Actions CI上で、pip-auditがOSVと
    PyPI Advisory Databaseの両方を照会した結果、同一のCVEが
    `vulns`配列内に重複して現れることを確認した
    (requests==2.32.3でPYSEC-2026-1872が2回報告された実例)。
    報告メッセージ内でこの重複がそのまま表示されず、1回だけ表示される
    ことを検証する(検出ロジックの正しさには影響しない表示上の整理)。"""
    stub = """
import json as _json

class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def _fake_run(cmd, *a, **kw):
    if "--version" in cmd:
        return _FakeCompleted(returncode=0, stdout="pip-audit 2.7.0")
    if "pip_audit" in cmd and "-r" in cmd:
        payload = {"dependencies": [
            {"name": "requests", "version": "2.32.3", "vulns": [
                {"id": "PYSEC-2026-1872", "fix_versions": ["2.32.4"], "description": "dup-source-1"},
                {"id": "PYSEC-2026-1872", "fix_versions": ["2.32.4"], "description": "dup-source-2"},
            ]},
        ]}
        return _FakeCompleted(returncode=0, stdout=_json.dumps(payload))
    return _FakeCompleted(returncode=0, stdout="")
"""
    res = _run_with_stubbed_subprocess(stub)
    assert res.returncode == 1, f"stdout={res.stdout} stderr={res.stderr}"
    assert res.stdout.count("PYSEC-2026-1872") == 1, (
        f"重複したvuln IDがそのまま表示されている: {res.stdout}"
    )


def test_zero_vulnerabilities_passes():
    """[回帰防止] pip-auditが脆弱性ゼロを報告した場合、正常にPASSし
    exit code 0になること(過剰検知で常に失敗するようになっていないか)。"""
    stub = """
import json as _json

class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def _fake_run(cmd, *a, **kw):
    if "--version" in cmd:
        return _FakeCompleted(returncode=0, stdout="pip-audit 2.7.0")
    if "pip_audit" in cmd and "-r" in cmd:
        payload = {"dependencies": [
            {"name": "requests", "version": "2.32.3", "vulns": []},
        ]}
        return _FakeCompleted(returncode=0, stdout=_json.dumps(payload))
    return _FakeCompleted(returncode=0, stdout="")
"""
    res = _run_with_stubbed_subprocess(stub)
    assert res.returncode == 0, f"stdout={res.stdout} stderr={res.stderr}"
    assert "PASS" in res.stdout


def test_unparseable_output_fails_closed():
    """[回帰防止] pip-auditがJSONとして解析できない出力を返した場合も、
    『安全である』と主張せずフェイルクローズドすること。"""
    stub = """
class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def _fake_run(cmd, *a, **kw):
    if "--version" in cmd:
        return _FakeCompleted(returncode=0, stdout="pip-audit 2.7.0")
    if "pip_audit" in cmd and "-r" in cmd:
        return _FakeCompleted(returncode=1, stdout="not json at all", stderr="some pip-audit internal error")
    return _FakeCompleted(returncode=0, stdout="")
"""
    res = _run_with_stubbed_subprocess(stub)
    assert res.returncode == 1, f"stdout={res.stdout} stderr={res.stderr}"
