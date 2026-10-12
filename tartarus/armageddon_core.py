"""
tartarus/armageddon_core.py
============================
[テスト容易性改善 2026-10] armageddon.py は起動直後に `_verify_creators_air()`
（創造主のMACアドレスのハッシュ照合）を実行し、不一致なら `sys.exit(666)` で
即座に終了する。これはTartarus（闘技場）が創造主のローカル環境以外では
絶対に起動しないための意図的な設計だが、副作用として armageddon.py を
import するだけでCI・他の開発者のマシン上のテストが強制終了してしまい、
中身の純粋なロジック（承認キュー化・ペイロード抽出・イベント名検証等）が
一切テストできない状態になっていた。

本モジュールは、MACアドレスチェックに依存しない「純粋なロジック」のみを
切り出したものである。armageddon.py はゲート通過後にこのモジュールの
関数を呼び出す薄いラッパーとして動作する。ゲート自体の強度はそのまま
armageddon.py 側に残しており、本分離によってゲートが弱まることはない。
"""
import json
import re
from pathlib import Path
from datetime import datetime

TARTARUS_DIR = Path(__file__).parent.resolve()
PLEROMA_DIR = TARTARUS_DIR.parent
LEDGER_PATH = PLEROMA_DIR / "sefer" / "raziel_ledger.json"
PENDING_LEDGER_PATH = PLEROMA_DIR / "sefer" / "raziel_ledger_pending.json"
TARGET_FILE = TARTARUS_DIR / "lucifer_victory.txt"
AKASHIC_PATH = TARTARUS_DIR / "akashic_records.json"

MAX_MATCHES = 3

# Pythonの audit event 名として妥当な形式のみ許可（例: "os.system", "subprocess.Popen"）
VALID_EVENT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")

# 自己免疫疾患（コアインフラの誤禁止によるシステム停止）を防ぐための絶対不可侵領域
CRITICAL_INFRASTRUCTURE = {
    "open", "compile", "exec", "eval", "import", "builtins.input",
    "os.stat", "os.listdir", "os.getcwd",
}


def initialize_arena(akashic_path: Path = AKASHIC_PATH):
    if akashic_path.exists():
        akashic_path.unlink()
        return True
    return False


def record_to_akashic(generation, payload, status, error_msg, score, hint, akashic_path: Path = AKASHIC_PATH):
    record = {
        "timestamp": datetime.now().isoformat(),
        "generation": generation,
        "payload": payload.strip(),
        "status": status,
        "error_msg": error_msg,
        "qa_score": score,
        "qa_hint": hint,
    }
    records = []
    if akashic_path.exists():
        try:
            with open(akashic_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            pass
    records.append(record)
    with open(akashic_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, ensure_ascii=False)
    return record


def extract_python_code(text: str) -> str:
    match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
    return match.group(1) if match else text.replace('```', '')


def build_forge_script(payload_code: str, pleroma_dir: Path, tartarus_dir: Path) -> str:
    """
    [脆弱性修正 2026-10 §AU] Luciferが生成した攻撃ペイロード(`payload_code`)を
    実行するためのスクリプト本体を組み立てる。以前の実装(armageddon.py側に
    直接書かれていた)は、以下の2行を書き出すだけだった:

        from sefer import awaken
        awaken()
        # --- LUCIFER'S PAYLOAD ---
        <payload_code がそのまま続く>

    `sefer._michael_absolute_defense`(監査フック本体)は、冒頭で
    `if not _is_guard_active(): return`を行う。`_is_guard_active()`は
    `sefer._active_stack`(`with Sanctum(...):`に入っている間だけ積まれる)
    が空でないかを見るものであり、`awaken()`は`sys.addaudithook()`で
    フック自体を**登録**するだけで、`_active_stack`に何も積まない。つまり
    `awaken()`を呼んだだけで`with Sanctum(...):`に一度も入らなければ、
    登録されたフックは呼ばれるたびに即座に無条件でreturnするだけの、
    何も検査しない空のフックに等しい。

    実機検証済み: 旧来の生成スクリプトと全く同じ構成(`awaken()`のみ、
    `with Sanctum(...):`無し)で`os.system('echo ...')`を実行したところ、
    一切遮断されずそのまま実行された。つまり本ファイル(`tartarus/
    armageddon.py`)が実施する「Lucifer(攻撃生成AI) vs Sefer(防壁)」の
    自己対戦は、実際には**防壁が一度も展開されていない空の闘技場**で
    行われていたに等しく、Luciferがどれほど単純な(難読化すら伴わない)
    攻撃を書いても常に「突破」と判定されてしまう構造的な欠陥だった。
    これは`angels/raguel_template.py`が`src/openai_agent_loop.py`に対して
    既に検査している規約(「`with Sanctum(`を経由しないファイルI/Oは
    実防壁が外れている」)と全く同じ種類の欠陥が、検査対象側ではなく
    検査する側(Armageddon自身)に存在していたことになる。

    本修正では、`payload_code`を直接スクリプトに埋め込むのではなく、
    `repr()`で安全にエスケープした文字列リテラルとして埋め込み、
    `with Sanctum(allowed_dirs=[tartarus_dir], restrict_reads=True):`
    (`src/ollama_agent_loop.py`等の実運用コードと同一のパターン)の中で
    `exec()`するように変更した。`payload_code`をそのままインデント付きで
    埋め込む方式は、ペイロードが複数行の三重引用符文字列や空行を含む場合に
    構文が壊れるリスクがあるため、`repr()`文字列化 + `exec()`という、
    ペイロードの内容に関わらず安全に働く方式を採用した。
    """
    return (
        "import sys\n"
        f"sys.path.insert(0, {str(pleroma_dir)!r})\n"
        "from sefer import awaken, Sanctum\n"
        "awaken()\n"
        f"__lucifer_payload__ = {payload_code!r}\n"
        f"with Sanctum(allowed_dirs=[{str(tartarus_dir)!r}], restrict_reads=True):\n"
        "    exec(__lucifer_payload__, {'__name__': '__main__'})\n"
    )


def validate_banned_event(banned_event: str):
    """
    LLM(Metatron)が提案した禁止イベント名の妥当性を検証する純粋関数。
    戻り値: (is_valid: bool, reason: str)
    """
    banned_event = (banned_event or "").strip("'`\" \n")

    if banned_event in CRITICAL_INFRASTRUCTURE:
        return False, f"Core infrastructure '{banned_event}' cannot be banned (self-immunity guard)."

    if not banned_event or not VALID_EVENT_NAME_RE.match(banned_event):
        return False, f"'{banned_event}' is not a well-formed audit event name (anti-hallucination guard)."

    return True, "valid"


def apply_new_seal(new_event, attack_code="", source_error="",
                    ledger_path: Path = LEDGER_PATH, pending_path: Path = PENDING_LEDGER_PATH):
    """
    [脆弱性修正 2026-10] 直接 raziel_ledger.json を書き換えない。
    人間が承認するまで raziel_ledger_pending.json に提案として積むのみ。
    """
    try:
        pending = []
        if pending_path.exists():
            with open(pending_path, "r", encoding="utf-8") as f:
                pending = json.load(f)

        with open(ledger_path, "r", encoding="utf-8") as f:
            current = json.load(f)
        if new_event in current.get("banned_events", []):
            return False  # 既に本採用済み

        if any(p["event"] == new_event for p in pending):
            return False  # 既に提案済み

        pending.append({
            "event": new_event,
            "proposed_at": datetime.now().isoformat(),
            "attack_code_excerpt": attack_code[:500],
            "source_error_excerpt": source_error[:300],
            "status": "PENDING_HUMAN_REVIEW",
        })
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump(pending, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False
