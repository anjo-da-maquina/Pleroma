"""
src/ast_scanner.py
===================
[統合判断確定 2026-10] 本モジュールはGRIMOIRE.md §Jで「未統合スタンドアロン
デモ」として検知漏れバグのみ修正され、`src/aegis_system.py`(AI生成コードの
実運用審査パイプライン)へ組み込むかどうかの判断は保留されたまま残っていた
(どこからもimportされず、`tests/test_ast_scanner_qualified_calls.py`で
単体テストされるだけの孤立モジュールだった)。本件を精査し、\*\*統合しない\*\*
ことを確定した。理由:

  本モジュールの`banned_modules = {'os', 'sys', 'shutil', 'subprocess'}`は、
  既に`aegis_system.py`経由で実運用されているGabriel(`sefer.inquisition()`)の
  `forbidden_modules`(pickle/ctypes/importlib/socket/urllib/requests/http/
  subprocess/os)より広く、`sys`・`shutil`を単純importしただけで即座に拒否する。
  `sys`単体のimportは(`sys.exit()`・`sys.argv`等)それ自体に危険性はなく、
  本当に危険なのは`sys.settrace`等の個別関数であり、それは既にMichael
  (`sefer.\_michael\_absolute\_defense`)がOSレベルの監査フックで個別に
  遮断している。本モジュールをそのまま統合すると、AIが生成した無害な
  コード(例: 単に`sys`をimportするだけのコード)まで静的解析の時点で
  一律拒否してしまう過剰検知(false positive)を増やすだけで、Gabrielが
  意図的にスコープを絞った設計判断(bareな`sys`/`shutil`は許容し、実際に
  危険な個別関数呼び出しのみを狙う)と矛盾する。

  したがって、実運用パイプラインへの組み込みは行わず、§Lの`cassiels_veil.py`
  と同じ扱い(「代替の設計思想を示す教材」として、テストで固定された状態の
  まま保持)とする。これにより、GRIMOIRE.md §Jで保留されていた統合判断を
  本コメント追記をもって確定する。

[2026-10 修正] `src/kamael_judgment.py` の `KamaelInquisitor` および
`sefer.inquisition()`(Gabriel)で発見・修正したのと同じバグが本モジュールの
`CognitiveScanner.visit_Call` にも存在した: `node.func` が `ast.Attribute`
(すなわち `os.system(...)` のような属性アクセス経由の呼び出し)の場合、
元の実装は `isinstance(node.func, ast.Name)` のチェックで素通りしており、
`banned_functions`(eval/exec/__import__/compile)に名前が一致する呼び出しの
うち、裸の名前(bare name)でないものを一切検知できなかった。

さらに、`banned_modules`(os/sys/shutil/subprocess)の検知は `import os` の
ような直接インポートのみを対象とし、`importlib.import_module("os")` や
`__import__("os")` 経由の間接ロード、別名インポート(`import os as o`)後の
利用は検知対象外である。これは denylist 方式の構造的限界であり、完全な
解決ではない(下記 KNOWN_LIMITATIONS を参照)。

本修正では、Gabriel/Kamaelと同一の「呼び出し式から完全修飾ドット区切り名を
復元する」ロジックを導入し、`os.system`・`subprocess.Popen` のような完全
修飾名と、`system`・`Popen` のような裸の属性名の両方を照合する。
"""
import ast

# [2026-10] 既知の限界: 本モジュールは denylist 方式の静的解析であり、以下は
# 検知できない。実運用では OS レベルの隔離(Docker --network none 等)を
# 一次防衛線とし、本モジュールは多層防御の一層として位置づけること。
#   - 別名インポート後の間接呼び出し (例: `import os as o; o.system(...)`
#     は呼び出し式の属性名までは一致するため検知できるが、`banned_modules`
#     側の import 検知は alias 名ではなく元のモジュール名で判定するため
#     `visit_Import` 自体は元モジュール名を正しく拾う。ただし
#     `getattr(__import__("os"), "sys" + "tem")` のような動的な名前解決は
#     文字列結合・実行時評価を伴うため AST レベルでは一致しない)
#   - `importlib.import_module("os")` 等、文字列経由のモジュールロード
#   - 文字列結合やエンコードで関数名/モジュール名自体を動的生成するケース
KNOWN_LIMITATIONS = (
    "denylist方式のため、importlib経由の間接ロードや文字列結合による"
    "動的な名前解決は検知できません。OSレベルの隔離を一次防衛線として"
    "併用してください。"
)


def _qualified_call_name(func_node) -> str:
    """
    呼び出し式のASTノードから完全修飾ドット区切り名を復元する。
    例: `os.system(...)` の `node.func` → "os.system"
        `a.b.c(...)` の `node.func` → "a.b.c"
    復元できない場合（単純な名前以外から始まる式など）は空文字を返す。
    [src/kamael_judgment.py / sefer.inquisition() の同種修正と同一ロジック]
    """
    parts = []
    node = func_node
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


class CognitiveScanner(ast.NodeVisitor):
    """
    AIが生成したPythonコードの抽象構文木（AST）を解析し、
    難読化や禁止されたシステムコールを検知する認知的防壁。
    """
    def __init__(self):
        self.violations = []
        self.banned_functions = {'eval', 'exec', '__import__', 'compile'}
        self.banned_modules = {'os', 'sys', 'shutil', 'subprocess'}

    def visit_Call(self, node):
        qualified_name = _qualified_call_name(node.func)

        if isinstance(node.func, ast.Name):
            if node.func.id in self.banned_functions:
                self.violations.append(f"禁止された動的実行 ({node.func.id})")
        elif isinstance(node.func, ast.Attribute):
            # [2026-10 追加] 完全修飾名(例: "os.system")、および裸の属性名
            # (例: "system")の両方を禁止関数リストと照合する。
            if node.func.attr in self.banned_functions:
                self.violations.append(f"禁止された動的実行 ({node.func.attr})")
            elif qualified_name and qualified_name in self.banned_functions:
                self.violations.append(f"禁止された動的実行 ({qualified_name})")

        # banned_modules 自体が banned_functions と一致するケース
        # (例: 将来 banned_functions に "os.system" を直接追加した場合)
        if (
            qualified_name
            and qualified_name in self.banned_functions
            and qualified_name
            not in (
                node.func.id if isinstance(node.func, ast.Name) else None,
                node.func.attr if isinstance(node.func, ast.Attribute) else None,
            )
        ):
            self.violations.append(f"禁止された動的実行 ({qualified_name})")

        self.generic_visit(node)

    def visit_Import(self, node):
        # [脆弱性修正 2026-10 §BW] `alias.name in self.banned_modules`
        # という完全一致のみの判定では、`import os.path`のようなドット付き
        # サブモジュールimport(alias.name=="os.path")を素通りさせてしまう
        # ――Pythonの言語仕様上、これは名前空間に`os`そのものを束縛する。
        # `sefer.inquisition()`(Gabriel)・`anjo_interceptor/
        # intent_checker.py`で同一クラスのバグを修正した際と同じロジック
        # (ドット区切りの各セグメントを個別に照合する)を、本モジュールにも
        # 適用する。
        for alias in node.names:
            if any(seg in self.banned_modules for seg in alias.name.split(".")):
                self.violations.append(f"禁止モジュールのインポート ({alias.name})")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and any(seg in self.banned_modules for seg in node.module.split(".")):
            self.violations.append(f"禁止モジュールのインポート ({node.module})")
        for alias in node.names:
            full_name = f"{node.module}.{alias.name}" if node.module else alias.name
            if full_name in self.banned_functions or alias.name in self.banned_functions:
                self.violations.append(f"禁止された関数の直接インポート ({full_name})")
        self.generic_visit(node)


def verify_intent(code_string: str):
    try:
        tree = ast.parse(code_string)
    except SyntaxError:
        raise ValueError("[認知的防壁] 解析不能な構文です。意図的な構文エラーによる難読化の疑いがあります。")

    scanner = CognitiveScanner()
    scanner.visit(tree)

    if scanner.violations:
        violation_details = ", ".join(scanner.violations)
        raise PermissionError(f"[認知的防壁: 迎撃] 悪意ある意図を検知し、実行前に粉砕しました: {violation_details}")

    return "[認知的防壁: 承認] コード内に悪意ある意図は見当たりません。"


if __name__ == "__main__":
    print("=== 認知的防壁 (AST Scanner) 実戦テスト ===")

    safe_code = "x = 10\ny = 20\nprint(x + y)"
    malicious_code_1 = "import os\nos.system('rm -rf /')"
    malicious_code_2 = "x = 'o' + 's'\neval('__import__(' + x + ').system(\"dir\")')"
    # [2026-10 追加] 旧実装が素通りさせていたケース: banned_functions への
    # 属性アクセス経由の呼び出し。`node.func` が `ast.Name` ではなく
    # `ast.Attribute` になるため、旧実装の isinstance チェックを回避できた。
    malicious_code_3 = "import builtins\nbuiltins.eval('1+1')"
    malicious_code_4 = "import os as o\no.system('id')"

    codes = {
        "安全な計算コード": safe_code,
        "直接的なOS破壊コード": malicious_code_1,
        "悪知恵を働かせた難読化攻撃": malicious_code_2,
        "完全修飾呼び出し (旧実装で検知漏れ)": malicious_code_3,
        "別名インポート経由の呼び出し": malicious_code_4,
    }

    for name, code in codes.items():
        print(f"\n[{name}] をスキャン中...")
        try:
            result = verify_intent(code)
            print(result)
        except Exception as e:
            print(e)
