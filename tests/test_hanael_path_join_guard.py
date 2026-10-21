"""
tests/test_hanael_path_join_guard.py
=======================================
[新設 2026-10 §BT] angels/hanael_path_join_guard.py の単体テスト。

本天使は、src/ollama_agent_loop.pyの_execute_safe_action()で実際に
発見した本物の脆弱性――`target = self.workspace_root / action_req.get
("target")`という素朴なパス結合(右辺が外部入力由来)が、secure_resolve()
等の検証を一度も経ずに直接ファイルI/Oへ使われていた――という
check-vs-useの不一致パターンを、一般化して検知する。

本テストは、(1) 基本的な検知能力、(2) 誤検知防止、(3) 実装中にレッド
チームとして自分自身をリポジトリ全体に対して実行して発見した、本物の
偽陽性(angels/sandalphon_decree.pyの完全固定リテラルパス3件)への対応を
固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import hanael_path_join_guard as hpg


def test_detects_the_real_sbt_bug_pattern():
    """[核心・§BTの再現] 外部入力由来の`/`結合パスが、検証を経ずに
    直接read_text()に使われている場合を検知する。"""
    text = (
        "class C:\n"
        "    def f(self, req):\n"
        "        target = self.workspace_root / req.get('target')\n"
        "        with Sanctum():\n"
        "            if True:\n"
        "                return target.read_text()\n"
    )
    findings = hpg.find_unsanitized_path_joins(text)
    assert len(findings) == 1
    assert findings[0][0] == "f" and findings[0][1] == "target"


def test_does_not_flag_when_secure_resolve_is_the_assignment_itself():
    """[回帰防止・§BTの修正の固定] src/ollama_agent_loop.pyの修正後の形
    ――`/`での素朴な結合ではなく、secure_resolve()の戻り値を直接代入する
    ――は、そもそも検知対象の形(`/`結合の代入)に当たらないため検知しない。"""
    text = (
        "class C:\n"
        "    def f(self, req):\n"
        "        try:\n"
        "            target = self.aegis.jail.secure_resolve(req.get('target', '.'))\n"
        "        except PermissionError as e:\n"
        "            raise SeferLossOfAtaraxia(str(e))\n"
        "        with Sanctum():\n"
        "            return target.read_text()\n"
    )
    assert hpg.find_unsanitized_path_joins(text) == []


def test_does_not_flag_when_sanitizer_called_between_join_and_use():
    """`/`結合の後、使用前に明示的にsecure_resolve()相当の検証関数が
    呼ばれていれば検知対象から外れる。"""
    text = (
        "class C:\n"
        "    def f(self, req):\n"
        "        target = self.workspace_root / req.get('target')\n"
        "        self.jail.secure_resolve(str(target))\n"
        "        return target.read_text()\n"
    )
    assert hpg.find_unsanitized_path_joins(text) == []


def test_known_false_positive_fixed_literal_trailing_segment_is_excluded():
    """[実装中の自己レッドチームで発見・即時修正の固定] 当初の実装は、
    `ROOT / "src" / "aegis_system.py"`のように、`/`結合の右辺(最後の
    要素)が完全な固定文字列リテラルである場合まで誤検知していた
    (angels/sandalphon_decree.pyで実際に3件の偽陽性を確認)。外部入力が
    混入する余地のない、完全に固定されたパスは検知対象から除外する。"""
    text = (
        "def f():\n"
        "    p = ROOT / 'src' / 'aegis_system.py'\n"
        "    return p.read_text()\n"
    )
    assert hpg.find_unsanitized_path_joins(text) == []


def test_detects_builtin_open_usage_too():
    """組み込みの`open()`に直接渡す形も検知する(属性呼び出し形式だけでなく)。"""
    text = (
        "def f(root, name):\n"
        "    target = root / name\n"
        "    with open(target) as fh:\n"
        "        return fh.read()\n"
    )
    findings = hpg.find_unsanitized_path_joins(text)
    assert len(findings) == 1 and findings[0][1] == "target"


def test_join_without_any_io_use_is_not_flagged():
    """`/`結合した後、ファイルI/Oに一度も使われない(例: 文字列化して
    返すだけ)場合は検知対象としない。"""
    text = (
        "def f(root):\n"
        "    p = root / 'fixed_name.txt'\n"
        "    return str(p)\n"
    )
    assert hpg.find_unsanitized_path_joins(text) == []


def test_file_with_no_slash_join_reports_not_applicable(monkeypatch, tmp_path, capsys):
    """`/`によるパス結合が一件も無いリポジトリ状態ではNOT_APPLICABLEを
    報告する(§BOで修正したPASS/NOT_APPLICABLE混同の再発防止)。"""
    (tmp_path / "angels").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "adapters").mkdir()
    (tmp_path / "anjo_interceptor").mkdir()
    (tmp_path / "src" / "clean.py").write_text("print('hello')\n", encoding="utf-8")
    monkeypatch.setattr(hpg, "ROOT", tmp_path)
    hpg.main()
    out = capsys.readouterr().out
    assert "⬜ NOT_APPLICABLE" in out


def test_real_repository_files_pass_after_the_sbt_fix():
    """[実機の裏付け] §BTで実際に修正したsrc/ollama_agent_loop.py
    ._execute_safe_action()を含む、現時点のリポジトリ全体に対して本天使を
    実行し、PASSすることを確認する(angels/sandalphon_decree.pyの偽陽性
    除外も含む回帰防止)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        hpg.main()
    assert "✅ PASS" in buf.getvalue()
