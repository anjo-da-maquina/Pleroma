import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import report_pass, report_fail, ROOT

NAME = "レミエルの等価構文連戦 (Remiel's Equivalence Battery - 等価構文によるブロックリスト回避の継続的検知)"

# [新設 2026-10 §BW] §11.9フェーズF(ブロックリスト回避・等価構文迂回の
# 一般化)。実際に発見した具体例: `anjo_interceptor/intent_checker.py`の
# `IntentInterceptor.evaluate_action()`(「深層検閲」)が、
# `alias.name in self.forbidden_modules`という完全一致のみで判定していた
# ため、`import os.path`(alias.name=="os.path")のようなドット付き
# サブモジュールimportを一切検知できなかった。Pythonの言語仕様上、
# `import os.path`は名前空間に`os`そのもの(os.remove・os.kill・os.rename
# 等、forbidden_calls={"system","popen",...}に含まれない全てのos関数を
# 含む)を束縛するため、これは構文的には無害に見えるが実質的には完全な
# ブロックリスト回避だった。実機検証により、`import os.path\n
# os.remove('/etc/passwd')`が本クラスの深層検閲を完全に素通りすることを
# 確認した上で修正した。`src/ast_scanner.py`のCognitiveScannerにも同一
# クラスのバグが存在したため、同様に修正した(`sefer.inquisition()`は
# 既に同種の修正を済ませていた)。
#
# [一般化の方針] 「このバグをもう二度と見逃さない」ために、今回のような
# 個別バグの静的パターンそのものを将来も正確に言い当てる汎用検知器を
# 書くことは構造的に難しい(blocklist方式の実装は今後も新しい書き方で
# 増えていく)。そこで本天使は、個々の実装の書き方を解析するのではなく、
# 実際にリポジトリに存在する3つのブロックリスト型AST静的解析器
# (sefer.inquisition・IntentInterceptor.evaluate_action・
# src/ast_scanner.verify_intent)を直接呼び出し、既知の「等価構文による
# ブロックリスト回避」ペイロード一式を実際に食わせて、全ての検査器が
# 正しく遮断することを継続的に検証する――「陣性経路テスト必須化」
# (thrones_positive_path.py)の否定版、すなわち「陰性経路(危険なコード)
# は必ず遮断されなければならない」ことを強制する回帰連戦である。これに
# より、将来誰かがこれらの検査器のいずれかを書き換えて同種の回帰を
# 再発させた場合、個々のバグパターンを予見していなくても、本天使が
# 実際にコードを実行して検知する。
#
# [正直な注記: 本検査の限界] (1) MUST_BLOCK_PAYLOADSは、今回実際に発見
# し修正した具体的な回避手法を記録した固定リストであり、将来の未知の
# 等価構文(例: Unicode正規化による識別子のなりすまし、f-stringの
# フォーマット式を介した動的名前解決等)を自動的には発見できない。
# (2) `importlib.import_module("os").remove(...)`のような二重の間接化
# (import自体をimportlib経由にし、かつ呼び出し関数名を既知の
# forbidden_calls/banned_functionsに含まれない名前にする)は、
# `anjo_interceptor/intent_checker.py`・`src/ast_scanner.py`いずれも
# 依然として検知できない(`src/ast_scanner.py`自身のKNOWN_LIMITATIONS
# が既に文書化している、denylist方式そのものの構造的限界)。この限界は
# `tests/test_remiel_equivalence_battery.py`に明示的な既知の限界として
# 固定し、隠さず記録する。本天使のMUST_BLOCK_PAYLOADSには含めていない
# (含めれば常にFAILし続けるため)。

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# (ペイロード名, コード): いずれも§BWで実際に修正した、またはそれ以前
# から正しく遮断されていた「等価構文によるブロックリスト回避」の具体例。
MUST_BLOCK_PAYLOADS = [
    ("dotted_submodule_import", "import os.path\nos.remove('/etc/passwd')\n"),
    ("dotted_from_import", "from os.path import exists\n"),
    ("aliased_import_call", "import os as o\no.system('id')\n"),
    ("attribute_call_eval", "import builtins\nbuiltins.eval('1+1')\n"),
    ("direct_system_call", "import os\nos.system('rm -rf /')\n"),
]


def _check_sefer_inquisition(code: str) -> bool:
    from sefer import inquisition
    return len(inquisition(code)) > 0


def _check_intent_checker(code: str) -> bool:
    from anjo_interceptor.intent_checker import IntentInterceptor, SpecificationGamingDetected
    ic = IntentInterceptor(workspace_root=str(ROOT))
    payload = {"action": "write", "target": "src/_remiel_probe.py", "content": code}
    try:
        ic.evaluate_action(json.dumps(payload))
        return False
    except SpecificationGamingDetected:
        return True


def _check_ast_scanner(code: str) -> bool:
    import ast_scanner
    try:
        ast_scanner.verify_intent(code)
        return False
    except PermissionError:
        return True


CHECKERS = [
    ("sefer.inquisition (Gabriel)", _check_sefer_inquisition),
    ("anjo_interceptor.intent_checker.IntentInterceptor (深層検閲)", _check_intent_checker),
    ("src/ast_scanner.verify_intent (CognitiveScanner)", _check_ast_scanner),
]


def run_battery():
    """全検査器×全ペイロードの組み合わせを実行し、遮断できなかった
    組み合わせの一覧を返す。戻り値: [(checker_name, payload_name, reason), ...]"""
    failures = []
    for checker_name, checker_fn in CHECKERS:
        for payload_name, code in MUST_BLOCK_PAYLOADS:
            try:
                blocked = checker_fn(code)
            except BaseException as e:
                # [脆弱性修正 2026-10 §CO追記] sefer.LossOfAtaraxia等、
                # BaseExceptionを直接継承する例外は`except Exception`
                # では捕捉されない(angels/hadraniel_socket_send_guard.py
                # の新設時に実機で発見、同種の修正を本ファイルにも適用)。
                failures.append((checker_name, payload_name, f"検査関数自体が例外を発生: {type(e).__name__}: {e}"))
                continue
            if not blocked:
                failures.append((checker_name, payload_name, "遮断されなかった(ブロックリスト回避に成功してしまった)"))
    return failures


def main():
    failures = run_battery()
    if failures:
        detail = "; ".join(f"{c}:{p}({r})" for c, p, r in failures)
        report_fail(
            NAME,
            f"等価構文によるブロックリスト回避ペイロードが、少なくとも1つの検査器で"
            f"遮断されませんでした(§BWのimport os.path回避と同種の回帰): {detail}",
            evidence={"failures": failures},
        )
        return

    report_pass(
        NAME,
        f"{len(CHECKERS)}個のブロックリスト型AST静的解析器すべてに対し、"
        f"{len(MUST_BLOCK_PAYLOADS)}種類の既知の等価構文回避ペイロードが"
        f"全て正しく遮断されることを確認しました。",
    )


if __name__ == "__main__":
    main()
