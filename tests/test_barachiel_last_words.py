"""
tests/test_barachiel_last_words.py
=====================================
[新設 2026-10 §BR] angels/barachiel_last_words.py の単体テスト。

本天使は、§BQで実機CIにおいて実際に発見した「os._exit()の直前に
flush()が無いため、自壊理由のログが(標準出力がパイプ/ファイルの場合に)
消失する」という、src/deadmans_switch.py・src/starvation_protocol.pyの
2件の本物のバグのパターンを、astによる静的解析で一般化して検知する。

本テストは、(1) 基本的な検知能力、(2) 誤検知防止、(3) 実装中にレッド
チームとして自分自身を試して発見した、正直な既知の限界を、実機の挙動
として固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import barachiel_last_words as blw


def test_detects_exit_with_no_preceding_flush():
    """[核心] os._exit()の前にflush()が一度も無い関数を検知する。"""
    text = (
        "import os\n"
        "def f():\n"
        "    print('bye')\n"
        "    os._exit(1)\n"
    )
    assert blw.find_unflushed_exits(text) == [("f", 4)]


def test_does_not_flag_exit_with_preceding_flush():
    """[回帰防止・§BQ修正の固定] flush()がos._exit()より前に呼ばれていれば
    検知しない(src/deadmans_switch.py・src/starvation_protocol.pyの修正後
    の形そのもの)。"""
    text = (
        "import os, sys\n"
        "def f():\n"
        "    print('bye')\n"
        "    sys.stdout.flush()\n"
        "    os._exit(1)\n"
    )
    assert blw.find_unflushed_exits(text) == []


def test_flush_via_variable_alias_is_still_recognized():
    """flush()の呼び出し元の変数名に関わらず(`sys.stdout`を直接書かなくても)、
    `.flush()`という属性呼び出しであれば汎用的に認識する。"""
    text = (
        "import os, sys\n"
        "def f():\n"
        "    out = sys.stdout\n"
        "    out.flush()\n"
        "    os._exit(1)\n"
    )
    assert blw.find_unflushed_exits(text) == []


def test_flush_only_after_exit_does_not_count():
    """[核心] os._exit()より後にflush()があっても(到達しないコードなので)
    無意味であり、検知対象とする。"""
    text = (
        "import os, sys\n"
        "def f():\n"
        "    os._exit(1)\n"
        "    sys.stdout.flush()\n"
    )
    assert blw.find_unflushed_exits(text) == [("f", 3)]


def test_flush_in_a_different_function_does_not_count():
    """他の関数内でflush()していても、os._exit()を呼ぶ関数自体にflushが
    無ければ検知対象とする(関数単位で独立に判定する)。"""
    text = (
        "import os, sys\n"
        "def helper():\n"
        "    sys.stdout.flush()\n"
        "def f():\n"
        "    os._exit(1)\n"
    )
    assert blw.find_unflushed_exits(text) == [("f", 5)]


def test_does_not_false_positive_on_comments_or_strings():
    """astベースの解析のため(正規表現ベースのthrones_positive_path.pyと
    異なり)、コメントや文字列リテラル中の`os._exit(1)`という見た目の
    テキストを誤検知しない。"""
    text = (
        "import os\n"
        "def f():\n"
        "    # 説明: os._exit(1) は危険\n"
        "    s = 'os._exit(1)'\n"
        "    print(s)\n"
    )
    assert blw.find_unflushed_exits(text) == []


def test_known_limitation_branch_insensitive_analysis():
    """[正直な既知の限界の固定・実装中の自己レッドチームで発見] 本検査は
    行番号の前後関係のみで判定しており、if/elseのような排他的な分岐構造
    までは解析しない。そのため、片方の分岐でのみflush()している場合でも、
    その分岐が別の分岐のos._exit()より前の行にあれば、誤って「flush済み」
    と判定してしまい、もう片方の分岐(本来flush漏れがある)を見逃す
    (偽陰性)。これは隠さず、実機の挙動として明示的に固定しておく。"""
    text = (
        "import os, sys\n"
        "def f(cond):\n"
        "    if cond:\n"
        "        sys.stdout.flush()\n"
        "        os._exit(1)\n"
        "    else:\n"
        "        os._exit(1)\n"
    )
    assert blw.find_unflushed_exits(text) == [], (
        "既知の限界(分岐非対応)が予期せず解消されている場合はこのテストを更新すること"
    )


def test_known_limitation_aliased_os_import_is_not_detected():
    """[正直な既知の限界の固定] `import os as _os`のようにosを別名で
    importしている場合、`_os._exit(1)`は検知できない。"""
    text = (
        "import os as _os\n"
        "def f():\n"
        "    _os._exit(1)\n"
    )
    assert blw.find_unflushed_exits(text) == []


def test_file_with_no_exit_call_reports_not_applicable(monkeypatch, tmp_path, capsys):
    """検査対象のos._exit()呼び出しが一件も無いリポジトリ状態では、
    NOT_APPLICABLEを報告する(§BOで修正したPASS/NOT_APPLICABLE混同の
    再発防止)。"""
    (tmp_path / "angels").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "adapters").mkdir()
    (tmp_path / "src" / "clean.py").write_text("print('no exit here')\n", encoding="utf-8")
    monkeypatch.setattr(blw, "ROOT", tmp_path)
    blw.main()
    out = capsys.readouterr().out
    assert "⬜ NOT_APPLICABLE" in out


def test_real_repository_files_pass_after_the_sbq_fix():
    """[実機の裏付け] §BQで実際に修正したsrc/deadmans_switch.py・
    src/starvation_protocol.pyを含む、現時点のリポジトリ全体に対して
    本天使を実行し、PASSすることを確認する(回帰防止)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        blw.main()
    assert "✅ PASS" in buf.getvalue()
