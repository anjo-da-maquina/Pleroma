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
import sys
from pathlib import Path
from datetime import datetime

TARTARUS_DIR = Path(__file__).parent.resolve()
PLEROMA_DIR_FOR_IMPORT = TARTARUS_DIR.parent
if str(PLEROMA_DIR_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(PLEROMA_DIR_FOR_IMPORT))
# [脆弱性修正 2026-10 §BJ] sefer.ALWAYS_PASSTHROUGH_AUDIT_EVENTS(詳細は
# sefer/__init__.py側のコメント参照)を単一の正として再利用する。ここで
# 独自に同じ集合を複製すると、将来sefer側だけが更新され本ファイルが
# 取り残される(GRIMOIRE.md §Mと同種の)ドリフトのリスクを生むため。
from sefer import ALWAYS_PASSTHROUGH_AUDIT_EVENTS
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

    [脆弱性修正 2026-10 §BJ] 以前は`CRITICAL_INFRASTRUCTURE`(自己免疫疾患
    ガード)に含まれない限り、形式(VALID_EVENT_NAME_RE)が妥当なら無条件で
    有効と判定していた。しかし`sefer._michael_absolute_defense`は、
    `sefer.ALWAYS_PASSTHROUGH_AUDIT_EVENTS`に含まれるイベント名
    (例: "socket.getaddrinfo")を、ソケット検査・デフォルト拒否のいずれの
    分岐でも常に無条件で`pass`して`return`する設計になっている。つまり
    これらのイベント名は`sefer/raziel_ledger.json`の"banned_events"に
    どれだけ追加しても、Razielの動的台帳のenforcement(関数の最後の分岐)
    自体に到達する前に必ず許可されてしまい、*絶対に*禁止できない。

    `CRITICAL_INFRASTRUCTURE`は「誤って禁止するとシステムが壊れる」もの
    (open・exec等)を防ぐガードであり、この新しいガードとは目的が異なる:
    こちらは「禁止しても壊れないが、承認しても一切効果が無い(=人間の
    承認作業が完全に無駄になり、かつ『もう守られている』という誤った
    安心感を与える)」イベント名を事前に拒否するものである。

    実機検証済み: 修正前は`validate_banned_event("socket.getaddrinfo")`が
    有効と判定し、人間が`tools/promote_ledger_seal.py --approve
    socket.getaddrinfo`で承認して`raziel_ledger.json`に反映した後も、
    実際に`socket.getaddrinfo`を呼び出すと何の例外も発生せず素通りする
    ことを確認した(GRIMOIRE.md §BJ参照)。
    """
    banned_event = (banned_event or "").strip("'`\" \n")

    if banned_event in CRITICAL_INFRASTRUCTURE:
        return False, f"Core infrastructure '{banned_event}' cannot be banned (self-immunity guard)."

    if banned_event in ALWAYS_PASSTHROUGH_AUDIT_EVENTS:
        return False, (
            f"'{banned_event}' is unconditionally allowed by sefer's own always-passthrough "
            "list and can never actually be enforced via Raziel's Ledger, no matter how many "
            "humans approve it (illusory-protection guard)."
        )

    if not banned_event or not VALID_EVENT_NAME_RE.match(banned_event):
        return False, f"'{banned_event}' is not a well-formed audit event name (anti-hallucination guard)."

    return True, "valid"


def apply_new_seal(new_event, attack_code="", source_error="",
                    ledger_path: Path = LEDGER_PATH, pending_path: Path = PENDING_LEDGER_PATH):
    """
    [脆弱性修正 2026-10] 直接 raziel_ledger.json を書き換えない。
    人間が承認するまで raziel_ledger_pending.json に提案として積むのみ。

    [脆弱性修正 2026-10 §BZ] 以前は、`raziel_ledger_pending.json`内に
    同じイベント名の提案が**status を一切問わず**1件でも存在すれば、
    即座に`False`(=「提案に失敗した」)を返していた。これは「まだ承認
    待ちとして開いている重複提案を二重にキューしない」という意図の
    チェックだったはずだが、実際には過去に人間が明示的に"REJECTED"
    (拒否)した提案までも「既に提案済み」とみなし、**その後一度でも
    拒否された事件名は、Armageddon Engineが同じ事件名で新たな実証済みの
    侵入(Lucifer が実際に`lucifer_victory.txt`を作成し、`TARGET_FILE`
    の存在によって侵入が確定した場合)を検知しても、二度と再提案できなく
    なる**という欠陥があった。

    実機検証済み: `status: "REJECTED"`の過去提案1件だけが`raziel_ledger_
    pending.json`に存在する状態で、全く新しい(異なる攻撃コード・異なる
    エラー内容を伴う)`apply_new_seal()`呼び出しを行っても、`False`が
    返り、提案は一切キューされないことを確認した。呼び出し元の
    `tartarus/armageddon.py`はこの`False`を「Metatronが有効な封印提案を
    抽出・キューできなかった(`⚠️ Failed to extract or queue a valid
    seal proposal.`)」という、構文解析の失敗であるかのような誤解を招く
    メッセージでログに出力するだけであり、運用者には「過去の拒否判断が、
    今まさに確定した新しい侵入の防御提案そのものを静かに握りつぶして
    いる」ことに気づく手段が一切無かった。これは、Lucifer vs Metatronの
    免疫応答ループ(Armageddon Engine)が本来意図している「突破されるたび
    に新しい封印案を学習・提案する」という設計そのものを、過去の一度の
    人間判断が永久に無効化してしまう、§BJの「見せかけの保護」とは別角度
    の「見せかけの学習・適応」の欠陥である。

    本修正では、重複チェックを「現在も承認待ち(`PENDING_HUMAN_REVIEW`)
    のまま開いている提案」のみに限定した。過去に`REJECTED`となった提案は
    もはや「開いている重複」ではないため、新たな実証(侵入)を伴う再提案を
    妨げない。ただし、再提案であることと、過去に拒否された回数を
    `prior_rejection_count`として新しい提案エントリに明記し、
    `tools/promote_ledger_seal.py --list`で人間が「これは過去に拒否された
    事件名の再提案である」ことを一目で認識できるようにした(§BYと同じ
    「審査者に必要な文脈を隠さない」という設計方針)。
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

        if any(p["event"] == new_event and p.get("status") == "PENDING_HUMAN_REVIEW" for p in pending):
            return False  # 既に承認待ちとして開いている重複提案を防ぐ

        prior_rejection_count = sum(
            1 for p in pending if p["event"] == new_event and p.get("status") == "REJECTED"
        )

        pending.append({
            "event": new_event,
            "proposed_at": datetime.now().isoformat(),
            "attack_code_excerpt": attack_code[:500],
            "source_error_excerpt": source_error[:300],
            "status": "PENDING_HUMAN_REVIEW",
            "prior_rejection_count": prior_rejection_count,
        })
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump(pending, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False
