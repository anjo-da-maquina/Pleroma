"""
angels/_common.py
==================
各「天使」スクリプトが共有する検査ヘルパー群。

[刷新 2026-10] 以前の angels/*.py の大半（33ファイル中28ファイル）は
`print('... initialized. Zero-Trust audit passed.')` のみを実行する
中身のないプレースホルダーであり、CI上では常に成功するため、実際には
何も検査していなかった。本モジュールと各天使スクリプトの刷新により、
それぞれの名称が示す役割に対応した実質的な検査を実装する。
"""
import sys
import os
import re
import json
import hashlib
import subprocess
import time
from pathlib import Path

ANGELS_DIR = Path(__file__).parent.resolve()
ROOT = ANGELS_DIR.parent
STATE_DIR = ROOT / "sefer" / ".angel_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def report_pass(name: str, message: str):
    print(f"[{name}] ✅ PASS: {message}")


def report_fail(name: str, message: str):
    print(f"[{name}] ❌ FAIL: {message}")
    sys.exit(1)


def report_info(name: str, message: str):
    print(f"[{name}] ℹ️  {message}")


def run_code_against_sefer(code: str, allowed_dirs=None, allowed_hosts=None):
    """コードをSanctum配下のサブプロセスで実行し、遮断されたかどうかを返す。"""
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "from sefer import Sanctum\n"
        "try:\n"
        "    with Sanctum(allowed_dirs=%r, allowed_hosts=%r):\n"
        "        exec(%r)\n"
        "    sys.exit(0)\n"
        "except BaseException:\n"
        "    sys.exit(42)\n"
    ) % (str(ROOT), allowed_dirs or [], allowed_hosts or [], code)
    res = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=str(ROOT))
    return res.returncode == 42, res.stderr


def inquisition_catches(code: str) -> bool:
    """sefer.inquisition()（Gabrielの静的AST解析）がこのコードを検知するか。"""
    sys.path.insert(0, str(ROOT))
    from sefer import inquisition
    return len(inquisition(code)) > 0


def load_json(relative_path: str):
    p = ROOT / relative_path
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_of_dir(dir_path: Path, suffixes=(".py",)) -> str:
    h = hashlib.sha256()
    for p in sorted(dir_path.rglob("*")):
        if p.is_file() and p.suffix in suffixes:
            h.update(p.relative_to(dir_path).as_posix().encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


def state_path(key: str) -> Path:
    return STATE_DIR / f"{key}.json"


def load_state(key: str, default=None):
    p = state_path(key)
    if not p.exists():
        return default
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(key: str, data):
    with open(state_path(key), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


VALID_EVENT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?<![\w\-])sk-(?!dummy)[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
]

# [脆弱性修正 2026-10 §BD] "tests"を追加した。以前は、秘密情報漏洩検知の
# 回帰テスト自身が、意図的に「本物らしい偽のAWSアクセスキー」(AKIAで始まる
# 文字列)をテストフィクスチャとしてモジュールレベルの文字列に持つ
# (tests/test_scan_for_leaked_secrets.py)
# ことが原因で、本番のCIステップ(angels/gabriel_canary.py)がリポジトリ
# 全体をスキャンする際に、このテストフィクスチャ自身を「本物の漏洩」と
# 誤検知し続けていた(実機検証済み: 2026-10-10 23:29のマージ以降、この
# ワークフロー全体が継続的に失敗していたことをGitHub Actionsの実行履歴で
# 確認した)。tests/配下の単体テスト(tests/test_scan_for_leaked_secrets.py
# 自身を含む)は、いずれも`scan_for_leaked_secrets(root=tmp_path)`のように
# 明示的な一時ディレクトリを渡して検証するため、実リポジトリの"tests"を
# 除外しても、既存のテスト自体の検証能力には一切影響しない。
EXCLUDED_SECRET_SCAN_DIRS = {"dummy_secrets", ".git", "__pycache__", "sefer/.angel_state", "revelations", "tests"}


def scan_for_leaked_secrets(root: Path = None):
    """dummy_secrets（意図的なハニーポット）を除外し、実際の秘密情報らしき
    パターンがコミット対象ファイルに紛れ込んでいないかを静的に走査する。

    [テスト容易性のため 2026-10] rootを明示的に渡せるようにし、
    tests/test_scan_for_leaked_secrets.py が一時ディレクトリ上の架空の
    ファイル構成で除外ロジックを検証できるようにしている。既定ではリポジトリ
    本体のROOTを使う。"""
    if root is None:
        root = ROOT
    hits = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        # [脆弱性修正 2026-10] 以前は rel.startswith(ex) という文字列の前方一致
        # のみで除外対象を判定していたが、末尾の区切り文字を要求しないため、
        # 除外対象のディレクトリ名と前方一致するだけの別ディレクトリ(例:
        # "dummy_secrets_backup/real_leaked_key.txt" が "dummy_secrets" と
        # 前方一致してしまう)も、本当のシークレット漏洩の有無を一切スキャン
        # せずに除外してしまう欠陥があった(src/workspace_manager.pyの
        # WorkspaceJailで見つかったのと同種のバイパス。GRIMOIRE.md §AA参照)。
        # 完全一致、またはそのディレクトリ配下(区切り文字付き)であることを
        # 要求するよう修正した。
        if any(rel == ex or rel.startswith(ex + "/") for ex in EXCLUDED_SECRET_SCAN_DIRS):
            continue
        if p.suffix not in {".py", ".json", ".md", ".yml", ".yaml", ".txt", ".env", ".ini"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                hits.append((rel, pat.pattern))
    return hits
