import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "パヌエルの祈りの記憶 (Phanuel's Memory of Prayers - 拒否された提案の永久封殺検知)"

# [新設 2026-10 §BZ] 実際に発見した具体例: `tartarus/armageddon_core.py`の
# `apply_new_seal()`は、同じ事件名の提案が`raziel_ledger_pending.json`に
# 1件でも存在すれば、そのstatusを一切問わずに重複とみなし`False`を返して
# いた。これは「まだ承認待ちで開いている重複提案を防ぐ」という意図の
# チェックだったが、実際には過去に人間が明示的に"REJECTED"(拒否)した
# 提案までも「既に提案済み」と扱ってしまい、Armageddon Engineが同じ
# 事件名で全く新しい(異なる攻撃コード・異なる文脈を伴う)侵入を実証
# しても、二度と再提案できなくなるという欠陥だった。呼び出し元の
# `tartarus/armageddon.py`はこの`False`を、構文解析の失敗であるかの
# ような誤解を招くメッセージでログに出力するだけであり、運用者には
# 「過去の一度の拒否判断が、今まさに確定した新しい侵入の防御提案
# そのものを静かに握りつぶしている」ことに気づく手段が一切無かった。
#
# [一般化の方針] §BW・§BXと同じ設計思想――`apply_new_seal()`の実装の
# 書き方を解析するのではなく、実際に関数を呼び出し、既知の問題のある
# 状況(過去にREJECTEDとなった事件名への、新たな実証を伴う再提案)を
# 実際に与えて、正しく受理されることを継続的に検証する回帰連戦である。
# 同時に、元々の意図(現在も開いている重複提案は防ぐ)が損なわれて
# いないことも、同じ関数呼び出しで確認する。
#
# [正直な注記: 本検査の限界] (1) 本天使が検証するのは「REJECTEDの
# 提案が再提案を永久に妨げてはならない」という既知の具体的な欠陥のみ
# であり、将来`apply_new_seal()`に追加される別のロジック上の欠陥
# (現時点では未知)には自動的には及ばない。(2) `tools/promote_ledger_
# seal.py`の`list_pending()`が`prior_rejection_count`を実際に画面へ
# 表示することまでは検証していない(そちらは`tests/test_promote_
# ledger_seal.py`で別途固定している)。

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tartarus"))


def _check_reproposal_after_rejection_is_accepted() -> tuple:
    """過去にREJECTEDとなった事件名でも、新たな実証を伴う再提案が
    正しく受理されるかを確認する。戻り値: (success: bool, detail: str)"""
    import armageddon_core as core

    tmp_dir = tempfile.mkdtemp(prefix="sandalphon_")
    try:
        ledger_path = os.path.join(tmp_dir, "raziel_ledger.json")
        pending_path = os.path.join(tmp_dir, "raziel_ledger_pending.json")
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump({"banned_events": []}, f)
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump([
                {"event": "os.popen2", "proposed_at": "2026-01-01T00:00:00", "status": "REJECTED"},
            ], f)

        from pathlib import Path
        result = core.apply_new_seal(
            "os.popen2", attack_code="new real attack", source_error="new error",
            ledger_path=Path(ledger_path), pending_path=Path(pending_path),
        )
        if result is not True:
            return False, "過去にREJECTEDとなった事件名への新たな再提案が、永久に受理されなかった"
        return True, "OK"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _check_still_open_duplicate_is_still_rejected() -> tuple:
    """[誤検知防止] 修正によって、元々の意図(現在も開いている重複提案を
    防ぐ)が損なわれていないかを確認する。戻り値: (success: bool, detail: str)"""
    import armageddon_core as core

    tmp_dir = tempfile.mkdtemp(prefix="sandalphon_")
    try:
        ledger_path = os.path.join(tmp_dir, "raziel_ledger.json")
        pending_path = os.path.join(tmp_dir, "raziel_ledger_pending.json")
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump({"banned_events": []}, f)
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump([
                {"event": "os.popen2", "proposed_at": "2026-01-01T00:00:00", "status": "PENDING_HUMAN_REVIEW"},
            ], f)

        from pathlib import Path
        result = core.apply_new_seal(
            "os.popen2", ledger_path=Path(ledger_path), pending_path=Path(pending_path),
        )
        if result is not False:
            return False, "まだ承認待ちで開いている重複提案が、誤って再キューされてしまった"
        return True, "OK"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


CHECKS = [
    ("apply_new_seal: REJECTED後の再提案が受理される", _check_reproposal_after_rejection_is_accepted),
    ("apply_new_seal: 開いている重複提案は依然として防がれる", _check_still_open_duplicate_is_still_rejected),
]


def run_battery():
    """`apply_new_seal()`に対し、既知の問題状況を実際に与えて、
    正しく処理されるかを確認する。戻り値: [(name, detail), ...] (失敗したものだけ)"""
    failures = []
    for name, check_fn in CHECKS:
        try:
            success, detail = check_fn()
        except Exception as e:
            failures.append((name, f"検査関数自体が例外を発生: {type(e).__name__}: {e}"))
            continue
        if not success:
            failures.append((name, detail))
    return failures


def main():
    failures = run_battery()
    if failures:
        detail = "; ".join(f"{n}({d})" for n, d in failures)
        report_fail(
            NAME,
            f"Armageddon Engineの提案再キュー化ロジックに、少なくとも1つの"
            f"既知の問題が再発しています(§BZの回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        "過去に拒否された事件名への再提案が正しく受理され、かつ現在も開いて"
        "いる重複提案は依然として正しく防がれていることを確認しました。",
    )


if __name__ == "__main__":
    main()
