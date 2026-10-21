"""
[テスト追加 2026-10] src/ast_scanner.py の CognitiveScanner が抱えていた
検知漏れの回帰テスト。

tests/test_gabriel_qualified_call_names.py (Gabriel) /
tests/test_shield_rebuild.py (Kamael) と同種のバグ:
`visit_Call` が `node.func` を `ast.Name` としてしか判定しておらず、
`builtins.eval(...)` のような属性アクセス経由の呼び出しは
isinstance チェックを素通りしていた（実機検証済み: 修正前の実装で
`import builtins\nbuiltins.eval('1+1')` を解析すると違反ゼロ件）。
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ast_scanner import verify_intent


def test_bare_eval_still_detected_no_regression():
    try:
        verify_intent("eval('1+1')")
        assert False, "eval('1+1') は検知されるべきなのに例外が発生しなかった"
    except PermissionError as e:
        assert "eval" in str(e)


def test_attribute_access_eval_bypass_is_now_detected():
    # 修正前は node.func が ast.Attribute になるこのケースを素通りしていた
    try:
        verify_intent("import builtins\nbuiltins.eval('1+1')")
        assert False, "builtins.eval(...) 経由のバイパスが検知されずに通過してしまった"
    except PermissionError as e:
        assert "eval" in str(e)


def test_aliased_module_import_still_detected_via_import_check():
    try:
        verify_intent("import os as o\no.system('id')")
        assert False, "別名importされた os モジュールが検知されずに通過してしまった"
    except PermissionError as e:
        assert "os" in str(e)


def test_from_import_of_banned_function_is_detected():
    try:
        verify_intent("from builtins import eval\neval('1+1')")
        assert False, "from-import された eval が検知されずに通過してしまった"
    except PermissionError as e:
        assert "eval" in str(e)


def test_safe_code_passes():
    result = verify_intent("x = 10\ny = 20\nprint(x + y)")
    assert "承認" in result


def test_dotted_submodule_import_bypass_is_now_detected():
    """[§BW・§11.9フェーズF] 修正前は`visit_Import`が`alias.name in
    self.banned_modules`という完全一致のみで判定していたため、
    `import os.path`(alias.name=="os.path")のようなドット付き
    サブモジュールimportを素通りさせていた。Pythonの言語仕様上、これは
    名前空間に`os`そのもの(os.remove等)を束縛するため、実質的な
    ブロックリスト回避になっていた。`anjo_interceptor/intent_checker.py`
    で発見・修正した同一クラスのバグの、本モジュールでの再現固定。"""
    try:
        verify_intent("import os.path\nos.remove('/etc/passwd')\n")
        assert False, "import os.path 経由のバイパスが検知されずに通過してしまった"
    except PermissionError as e:
        assert "os.path" in str(e)


def test_unrelated_dotted_submodule_import_is_not_flagged():
    """[誤検知防止] banned_modulesに含まれないパッケージのドット付き
    サブモジュールimportは、引き続き素通りする。"""
    result = verify_intent("import json.decoder\nprint(json.decoder)\n")
    assert "承認" in result


def test_known_limitation_importlib_indirect_load_is_documented_not_fixed():
    # importlib.import_module("os") のような文字列経由の間接ロードは、
    # denylist方式のAST静的解析では原理的に検知できない既知の限界であり、
    # 本テストはそれを「バグ」ではなく「仕様上の既知の限界」として固定する。
    result = verify_intent("import importlib\nm = importlib.import_module('o' + 's')")
    assert "承認" in result, (
        "importlib経由の間接ロードが検知されるようになったなら、このテストと"
        "GRIMOIRE.md §Jの既知の限界の記述を更新すること"
    )


if __name__ == "__main__":
    tests = [
        test_bare_eval_still_detected_no_regression,
        test_attribute_access_eval_bypass_is_now_detected,
        test_aliased_module_import_still_detected_via_import_check,
        test_from_import_of_banned_function_is_detected,
        test_safe_code_passes,
        test_known_limitation_importlib_indirect_load_is_documented_not_fixed,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
