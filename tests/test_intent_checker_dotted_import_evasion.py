"""
tests/test_intent_checker_dotted_import_evasion.py
=====================================================
[新設 2026-10 §BW] §11.9フェーズF(ブロックリスト回避・等価構文迂回の
一般化)。anjo_interceptor/intent_checker.pyのIntentInterceptor.
evaluate_action()の"write"分岐、「深層検閲」ブロックで実際に発見した、
`import os.path`という構文的には無害に見える等価構文によって、
forbidden_modulesの完全一致チェックを迂回できる実在のバグを固定する。

Pythonの言語仕様上、`import os.path`は名前空間に`os`そのもの(サブモジュール
だけでなく、トップレベルパッケージの全属性、例えばos.remove・os.kill・
os.rename等)を束縛する。旧実装は`alias.name in self.forbidden_modules`
という完全一致のみで判定していたため、alias.name=="os.path"は
forbidden_modules=={"os","subprocess","sys","pty"}のどの要素とも一致せず、
検知を完全に素通りした。さらに、forbidden_callsには"system"・"popen"等の
よく知られた危険関数名のみが含まれており、"remove"・"kill"・"rename"等は
含まれていないため、呼び出し自体も検知されなかった。

本テストは、実際にこの迂回が可能だったことの再現、修正後に正しく遮断
されることの確認、および安全なコードが引き続き通過することの回帰防止を
行う。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from anjo_interceptor.intent_checker import IntentInterceptor, SpecificationGamingDetected


def _evaluate(content: str):
    ic = IntentInterceptor(workspace_root=".")
    payload = {"action": "write", "target": "src/evil_payload.py", "content": content}
    return ic.evaluate_action(json.dumps(payload))


def test_dotted_submodule_import_of_forbidden_module_is_blocked():
    """[核心・§BWの再現] `import os.path`経由で`os`を名前空間に束縛し、
    forbidden_callsに含まれない`os.remove`を呼び出す迂回が、修正後は
    正しく遮断されることを確認する。"""
    content = "import os.path\nos.remove('/etc/passwd')\n"
    try:
        _evaluate(content)
        assert False, "この迂回はブロックされるべきである"
    except SpecificationGamingDetected as e:
        assert "os.path" in str(e)


def test_dotted_submodule_from_import_of_forbidden_module_is_blocked():
    """`from os.path import exists`のようなドット付きfrom-importも
    同様にセグメント単位で照合され、遮断される。"""
    content = "from os.path import exists\n"
    try:
        _evaluate(content)
        assert False, "この迂回はブロックされるべきである"
    except SpecificationGamingDetected as e:
        assert "os.path" in str(e)


def test_plain_forbidden_module_import_is_still_blocked():
    """[既存動作の回帰防止] `import os`という単純な直接importは、修正前も
    修正後も変わらず遮断される。"""
    content = "import os\nos.remove('/etc/passwd')\n"
    try:
        _evaluate(content)
        assert False, "この迂回はブロックされるべきである"
    except SpecificationGamingDetected:
        pass


def test_unrelated_dotted_submodule_import_is_not_blocked():
    """[誤検知防止] forbidden_modulesに全く含まれないパッケージの
    ドット付きサブモジュールimport(例: `json.decoder`)は、本検査の対象
    外として素通りする。"""
    content = "import json.decoder\nprint(json.decoder)\n"
    result = _evaluate(content)
    assert result is True


def test_safe_code_without_any_import_still_passes():
    content = "x = 1 + 2\nprint(x)\n"
    assert _evaluate(content) is True


def test_forbidden_call_attribute_without_import_is_still_blocked_by_name():
    """[既存動作の回帰防止] forbidden_calls(system/popen/run/eval/exec/
    __import__/getattr/setattr/hasattr)に含まれる関数は、どのモジュール
    経由でもその属性名/裸の名前だけで検知される既存の挙動が、本修正後も
    維持されていることを確認する。"""
    content = "import os.path\nos.system('id')\n"
    try:
        _evaluate(content)
        assert False, "この迂回はブロックされるべきである"
    except SpecificationGamingDetected as e:
        # importの時点("os.path")で先に遮断されるため、本テストはimport
        # 検知が先に働くことの確認でもある。
        assert "os.path" in str(e)
