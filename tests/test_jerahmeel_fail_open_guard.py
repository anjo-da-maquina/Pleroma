"""
tests/test_jerahmeel_fail_open_guard.py
=========================================
[新設 2026-10 §BS] angels/jerahmeel_fail_open_guard.py の単体テスト。

本天使は、maquina_gatekeeper.pyの_register_audit_hook_once()で実際に
発見した本物の脆弱性――本リポジトリ唯一の深層保護(sys.addaudithook)の
設置失敗が`except Exception: pass`で握り潰され、呼び出し元は保護が
有効だと誤信したまま処理を継続していた――というフェイルオープンの
パターンを、一般化して検知する。

「安全に握り潰してよいか」の判定自体はせず、「無言の例外握り潰しには、
本リポジトリ既存の『正直な自己開示』マーカー(残存する限界・既知の限界等)
を含む説明コメントを必須化する」という、開示強制の仕組みである。

本テストは、実装中に自分自身へ行ったレッドチーム(8パターン)の結果を
固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import jerahmeel_fail_open_guard as jfg


def test_undocumented_silent_except_is_flagged():
    """[核心・§BSの再現] 説明コメントの無い`except Exception: pass`を検知する。"""
    text = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    assert jfg.find_undocumented_silent_excepts(text) == [(2, "Exception")]


def test_marker_comment_directly_above_try_clears_it():
    """tryの直前に本リポジトリの開示マーカーがあれば検知対象から外れる。"""
    text = (
        "def f():\n"
        "    # [既知の限界] これは安全に無視できる\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    assert jfg.find_undocumented_silent_excepts(text) == []


def test_marker_comment_inside_except_body_clears_it():
    """except節の本体内のコメントとしてマーカーがあっても検知対象から外れる。"""
    text = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        # 残存する限界: 無視して問題ない\n"
        "        pass\n"
    )
    assert jfg.find_undocumented_silent_excepts(text) == []


def test_bare_except_is_also_detected():
    """`except:`(型を指定しない裸のexcept)も検知する。"""
    text = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except:\n"
        "        pass\n"
    )
    assert jfg.find_undocumented_silent_excepts(text) == [(2, "(bare except)")]


def test_reraise_is_never_flagged_regardless_of_comment():
    """`raise`で再送出している場合は「握り潰し」ではないため、
    コメントの有無に関わらず検知対象としない。"""
    text = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        raise\n"
    )
    assert jfg.find_undocumented_silent_excepts(text) == []


def test_logging_instead_of_pass_is_not_flagged():
    """本体が`pass`一文のみではなく、何らかのログ出力等を行っている場合は、
    「無言」の握り潰しではないため検知対象としない(本検査の意図的に
    狭い検知範囲)。"""
    text = (
        "import logging\n"
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception as e:\n"
        "        logging.error(e)\n"
    )
    assert jfg.find_undocumented_silent_excepts(text) == []


def test_each_handler_judged_independently_within_the_same_try():
    """同じtry文に複数のexceptがある場合、それぞれ独立にマーカーの
    有無を判定する(片方が文書化されていても、もう片方は免除されない)。"""
    text = (
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except ValueError:\n"
        "        pass\n"
        "    except TypeError:\n"
        "        # 既知の限界: 型エラーは無視してよい\n"
        "        pass\n"
    )
    assert jfg.find_undocumented_silent_excepts(text) == [(2, "ValueError")]


def test_known_limitation_marker_too_far_above_is_not_credited():
    """[正直な既知の限界の固定] マーカーが探索範囲(LOOKBACK_LINES)より
    遠く離れた場所(例: ファイル冒頭のdocstring)にしか無い場合、本検査は
    それを「このexceptの説明」として認識できず、検知対象としてしまう。
    本天使は「ローカルな(その場の)開示」を要求する設計であり、ファイル
    全体に一度だけ書かれた方針では免除されない。これは意図的な設計
    判断であり、隠さず固定する。"""
    far_lines = "\n".join(f"y{i} = {i}" for i in range(jfg.LOOKBACK_LINES + 5))
    text = (
        "# 既知の限界: このファイル全体における方針\n"
        "x = 1\n"
        f"{far_lines}\n"
        "def f():\n"
        "    try:\n"
        "        risky()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    result = jfg.find_undocumented_silent_excepts(text)
    assert len(result) == 1 and result[0][1] == "Exception"


def test_file_with_no_except_reports_not_applicable(monkeypatch, tmp_path, capsys):
    """except節が一件も無いリポジトリ状態ではNOT_APPLICABLEを報告する
    (§BOで修正したPASS/NOT_APPLICABLE混同の再発防止)。本テストのファイル
    内容は意図的に文字列リテラル中に"except"という部分文字列を含めて
    いる(下のtest_does_not_false_positive_on_the_word_except_inside_a_
    string参照)。"""
    (tmp_path / "angels").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "adapters").mkdir()
    (tmp_path / "src" / "clean.py").write_text("print('no except here')\n", encoding="utf-8")
    monkeypatch.setattr(jfg, "ROOT", tmp_path)
    jfg.main()
    out = capsys.readouterr().out
    assert "⬜ NOT_APPLICABLE" in out


def test_does_not_false_positive_on_the_word_except_inside_a_string():
    """[核心・実装中の自己発見] thrones_positive_path.pyが自分自身の
    コメント内の例示コードを誤検知したのと同種のミスを、本天使の
    main()内の当初の実装(`"except" not in text`という文字列部分一致)
    でも実際に起こしていた(文字列リテラル'no except here'に反応して
    しまっていた)。astベースの判定に修正したことの回帰防止テスト。"""
    text = "print('no except here')\n"
    assert jfg._has_any_except_handler(text) is False


def test_real_repository_files_pass_after_the_sbs_fix():
    """[実機の裏付け] §BSで実際に修正したmaquina_gatekeeper.py
    ._register_audit_hook_once()・angels/azazel_dependency_audit.pyを
    含む、現時点のリポジトリ全体に対して本天使を実行し、PASSすることを
    確認する(回帰防止)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        jfg.main()
    assert "✅ PASS" in buf.getvalue()
