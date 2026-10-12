"""
[新規発見 2026-10 §AY] sefer.inquisition()(Gabrielの静的AST解析)の denylist
方式には、`sys.modules['os'].system(...)` のような、`ast.Subscript`(辞書
アクセス)経由でモジュールを取得する間接呼び出しを検知できない構造的な
抜け穴がある。

`inquisition()`の`_qualified_call_name()`は`ast.Attribute`/`ast.Name`の
連鎖しか辿らないため、`sys.modules['os'].system`のような式は、`.value`が
`ast.Subscript`(`sys.modules['os']`の部分)である時点で再帰が止まり、
完全修飾名を復元できない。また呼び出し式の末端の属性名は`"system"`のみで
あり、`forbidden_funcs`に含まれる`"os.system"`(ドット付き完全修飾名)とは
一致しない。さらに`"sys"`自体は`forbidden_modules`に含まれていないため、
`import sys`の行も検知されない。結果として`inquisition()`はこのコードに対し
一件のFindingも返さない(本テストの`test_gabriel_misses_sys_modules_subscript_bypass`
で固定)。

しかし、本番でAI生成コードを実行する唯一の経路(`src/aegis_system.py`の
`execute_ai_intent()`、および`src/ollama_agent_loop.py`等の実運用ループ)は、
Gabrielの静的解析だけで実行を許可するのではなく、実際の動的実行を必ず
`with Sanctum(...):`のコンテキスト内で行う。Sanctumの監査フック
(`sefer._michael_absolute_defense`、Michael)はPythonのaudit event
(`os.system`)をCレベルで捕捉するため、Pythonコード側がどのような属性
アクセス経路でそこに到達したか(`os.system(...)`直接呼び出しか、
`sys.modules['os'].system(...)`経由か)に関わらず、確実に遮断する
(本テストの`test_michael_still_blocks_the_bypass_at_execution_time`で
固定)。

つまり本件は、Gabrielの静的解析単体には実在する抜け穴があるが、実際に
コードを実行する唯一の本番経路では、Michaelの動的・OSレベルの防壁が
正しくそれを補っている、という多層防御が意図通りに機能している例である。
`src/ast_scanner.py`のKNOWN_LIMITATIONSが既に一般論として「denylist方式の
静的解析には限界があり、OSレベルの隔離を一次防衛線とすべき」と述べていた
通りの構造が、`sefer.inquisition()`自身(教材ではなく実運用コード)にも
具体的に当てはまることを、本テストで実機検証として固定する。

[未解決の残存リスク] `angels/sariel_fallen_auditor.py`(CI上で`adapters/`
配下のスクリプトをGabrielの静的解析のみで検査する)は、この種のコードに
対して動的実行を一切行わないため、本バイパスに対して無力である。ただし
`adapters/`はAIが生成する未検証コードではなく保守者が書く内部ツールである
ため、実害の想定は低いと判断し、今回は`sariel_fallen_auditor.py`自体の
修正は行わず、この限界を正直に記録するに留める。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sefer import inquisition, awaken, Sanctum, LossOfAtaraxia

_BYPASS_PAYLOAD = "import sys\nsys.modules['os'].system('echo should_be_blocked')\n"


def test_gabriel_misses_sys_modules_subscript_bypass():
    """[既知の限界の固定] Gabrielの静的解析は、sys.modules['os']という
    Subscript経由の間接アクセスを一件も検知しない。"""
    findings = inquisition(_BYPASS_PAYLOAD)
    assert findings == [], (
        "この既知の限界が無くなった(Gabrielが検知できるようになった)場合は、"
        "本テストを更新し、GRIMOIRE.md §AYの記述も合わせて見直すこと。"
        f" findings={findings}"
    )


def test_michael_still_blocks_the_bypass_at_execution_time():
    """[多層防御の核心] Gabrielの静的解析をすり抜けても、実際にSanctumの
    中で実行すれば、MichaelのOSレベル監査フックが確実に遮断する。"""
    awaken()
    try:
        with Sanctum(allowed_dirs=[], allowed_hosts=[]):
            exec(_BYPASS_PAYLOAD, {})
        assert False, "Michaelがsys.modules経由のos.system呼び出しを遮断しなかった"
    except LossOfAtaraxia as e:
        assert "os.system" in str(e)
