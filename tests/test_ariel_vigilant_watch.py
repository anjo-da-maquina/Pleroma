"""
tests/test_ariel_vigilant_watch.py
=====================================
[新設 2026-10 §BU] angels/ariel_vigilant_watch.py の単体テスト。

本天使は、tests/test_angels_scripts_wired_into_ci.pyで実際に発見・修正
した自己言及的な欠陥――CIワークフロー上のステップに`if: false`を追加
するだけで、天使を実質的に無効化できるにもかかわらず、既存の「配線
漏れ検知」テストはそれを見逃していた――を一般化し、angels/*.pyに限らず
全てのCIステップに対して継続的に検査する。

本テストは、実装中に自分自身へ行ったレッドチーム(7パターン)の結果を
固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "angels"))
import ariel_vigilant_watch as avw


def test_detects_literal_boolean_false():
    """[核心・§BUの再現] `if: false`(YAML上のブール値False)で無効化
    されたステップを検知する。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: sabotaged\n"
        "        if: false\n"
        "        run: python angels/x.py\n"
    )
    assert avw.find_disabled_steps(text) == [("j", "sabotaged")]


def test_does_not_flag_normal_success_condition():
    """`if: success()`のような通常の条件は検知対象としない。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: normal\n"
        "        if: success()\n"
        "        run: python angels/x.py\n"
    )
    assert avw.find_disabled_steps(text) == []


def test_detects_quoted_expression_form_of_false():
    """`if: '${{ false }}'`のように、GitHub Actionsの式構文で囲まれた
    falseも検知する。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: quoted-false\n"
        "        if: \"${{ false }}\"\n"
        "        run: python angels/x.py\n"
    )
    assert avw.find_disabled_steps(text) == [("j", "quoted-false")]


def test_detects_numeric_zero():
    """`if: 0`も常に偽として検知する。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: zero\n"
        "        if: 0\n"
        "        run: python angels/x.py\n"
    )
    assert avw.find_disabled_steps(text) == [("j", "zero")]


def test_detects_empty_string_condition():
    """`if: ''`(空文字列)も常に偽として検知する。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: empty-string-if\n"
        "        if: ''\n"
        "        run: python angels/x.py\n"
    )
    assert avw.find_disabled_steps(text) == [("j", "empty-string-if")]


def test_does_not_flag_uses_only_steps_even_with_if_false():
    """[意図的に狭い検知範囲] `run:`を持たない`uses:`ステップは、
    そもそも本検査の対象外とする(呼び出すアクション自体の無効化は
    別の関心事)。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: no-run-just-uses\n"
        "        if: false\n"
        "        uses: actions/checkout@v4\n"
    )
    assert avw.find_disabled_steps(text) == []


def test_known_limitation_dynamic_condition_is_not_evaluated():
    """[正直な既知の限界の固定] `steps.foo.outcome == 'failure'`のような、
    実行時にしか決まらない動的な条件は、静的には「常に偽」と判定できない
    ため検知対象外とする。これは意図的な設計上の限界であり、隠さず固定
    する。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: cond-on-prior-step\n"
        "        if: steps.foo.outcome == 'failure'\n"
        "        run: python angels/x.py\n"
    )
    assert avw.find_disabled_steps(text) == []


def test_no_workflow_files_reports_not_applicable(monkeypatch, tmp_path, capsys):
    """ワークフローファイルが一件も無い状態ではNOT_APPLICABLEを報告する
    (§BOで修正したPASS/NOT_APPLICABLE混同の再発防止)。"""
    empty_wf_dir = tmp_path / ".github" / "workflows"
    empty_wf_dir.mkdir(parents=True)
    monkeypatch.setattr(avw, "ROOT", tmp_path)
    monkeypatch.setattr(avw, "TARGET_WORKFLOW_DIR", empty_wf_dir)
    avw.main()
    out = capsys.readouterr().out
    assert "⬜ NOT_APPLICABLE" in out


def test_real_repository_workflows_pass():
    """[実機の裏付け] 現時点のリポジトリの実際のワークフローファイルに
    対して本天使を実行し、PASSすることを確認する(回帰防止)。"""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        avw.main()
    assert "✅ PASS" in buf.getvalue()
