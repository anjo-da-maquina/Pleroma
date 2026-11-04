"""
tests/test_check_ci_step_disabled.py
=====================================
[新設 2026-10 §BU] angels/check_ci_step_disabled.py の単体テスト。

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
import check_ci_step_disabled as avw


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


def test_detects_continue_on_error_with_no_downstream_outcome_check():
    """[核心・新設 2026-11] `continue-on-error: true`が設定されている
    のに、同じジョブ内のどの後続ステップもそのoutcome/conclusionを
    一度も参照していない場合、失敗が黙って握り潰されたまま伝播しない
    (=ジョブ全体が誤ってgreenになり得る)ことを検知する。
    `.github/workflows/sanctuary_ci.yml`の§BQ修正(outcome enforcement
    の追加)を、実際にその行を取り除いて再現し、本検査が正しくこの
    状態を検知することを確認済み。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: Execute Sanctuary Verification\n"
        "        id: sanctuary_verify\n"
        "        continue-on-error: true\n"
        "        run: pytest tests/\n"
        "      - name: unrelated next step\n"
        "        run: echo done\n"
    )
    result = avw.find_unchecked_continue_on_error_steps(text)
    assert len(result) == 1
    assert result[0][0] == "j"
    assert result[0][1] == "Execute Sanctuary Verification"


def test_does_not_flag_continue_on_error_whose_outcome_is_checked():
    """`continue-on-error: true`のステップでも、後続ステップが
    `steps.<id>.outcome`を実際に参照していれば誤検知しない(§BQの
    修正後の正しい状態そのもの)。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: Execute Sanctuary Verification\n"
        "        id: sanctuary_verify\n"
        "        continue-on-error: true\n"
        "        run: pytest tests/\n"
        "      - name: enforce\n"
        "        if: steps.sanctuary_verify.outcome == 'failure'\n"
        "        run: exit 1\n"
    )
    assert avw.find_unchecked_continue_on_error_steps(text) == []


def test_does_not_flag_continue_on_error_checked_via_conclusion():
    """`.outcome`ではなく`.conclusion`を参照する形でも、同様に正しく
    「参照されている」と判定する。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: step-a\n"
        "        id: step_a\n"
        "        continue-on-error: true\n"
        "        run: pytest tests/\n"
        "      - name: enforce\n"
        "        run: |\n"
        "          if [ \"${{ steps.step_a.conclusion }}\" = \"failure\" ]; then exit 1; fi\n"
    )
    assert avw.find_unchecked_continue_on_error_steps(text) == []


def test_detects_continue_on_error_step_with_no_id_at_all():
    """`continue-on-error: true`だがidすら設定されていない場合、他の
    どのステップも原理的にそのoutcomeを参照できないため、より明確な
    理由付きで検知する。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: no-id-step\n"
        "        continue-on-error: true\n"
        "        run: pytest tests/\n"
    )
    result = avw.find_unchecked_continue_on_error_steps(text)
    assert len(result) == 1
    assert "id" in result[0][2]


def test_does_not_flag_steps_without_continue_on_error():
    """`continue-on-error`が設定されていない通常のステップは、この検査
    の対象にならない(誤検知しない)。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: normal\n"
        "        id: normal_step\n"
        "        run: pytest tests/\n"
    )
    assert avw.find_unchecked_continue_on_error_steps(text) == []


def test_continue_on_error_false_is_not_flagged():
    """`continue-on-error: false`(明示的に無効)は検知対象にしない。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: normal\n"
        "        id: normal_step\n"
        "        continue-on-error: false\n"
        "        run: pytest tests/\n"
    )
    assert avw.find_unchecked_continue_on_error_steps(text) == []


def test_battery_detects_reintroduced_sanctuary_ci_regression(monkeypatch):
    """[自己レッドチームの固定] `.github/workflows/sanctuary_ci.yml`から
    outcome enforcementの行を実際に取り除いて再現し(§BQ規模の退行)、
    本天使のmain()が正しくFAILすることを実機で確認した(git diff --stat
    で変更ファイルを正確に元へ復元したことも確認済み)。ここではmain()
    そのものを、一時ディレクトリ上の最小再現ワークフローに対して実行する
    形で、同じ退行を継続的に固定する。"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        wf_dir = Path(td) / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "sabotaged.yml").write_text(
            "jobs:\n"
            "  verify_ataraxia:\n"
            "    steps:\n"
            "      - name: Execute Sanctuary Verification\n"
            "        id: sanctuary_verify\n"
            "        continue-on-error: true\n"
            "        run: pytest tests/\n"
            "      - name: 失敗時の詳細をコミットコメントとして可視化\n"
            "        run: echo no-outcome-check-here\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(avw, "ROOT", Path(td))
        monkeypatch.setattr(avw, "TARGET_WORKFLOW_DIR", wf_dir)
        try:
            avw.main()
            assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
        except SystemExit as e:
            assert e.code == 1


def test_detects_job_level_always_false_condition():
    """[核心・新設 2026-11・§CVの直後] ジョブ定義自身の`if:`が常に偽の
    場合、そのジョブ配下の全ステップが丸ごと実行されないにもかかわらず、
    既存の`find_disabled_steps`(ステップ単位のみを見る)はこれを一度も
    検知しなかった。`.github/workflows/sanctuary_ci.yml`に実際に
    `if: false`をジョブ定義直下へ一時的に追加して再現し、本検査が正しく
    検知することを実機で確認済み(git diff --statで完全に復元したことも
    確認済み)。"""
    text = (
        "jobs:\n"
        "  verify_ataraxia:\n"
        "    if: false\n"
        "    steps:\n"
        "      - name: step1\n"
        "        run: pytest tests/\n"
    )
    assert avw.find_disabled_jobs(text) == ["verify_ataraxia"]


def test_does_not_flag_job_level_dynamic_condition():
    """ジョブレベルの`if: success()`のような通常の(他のジョブの結果に
    依存する)動的条件は検知対象としない。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    if: success()\n"
        "    steps:\n"
        "      - name: step1\n"
        "        run: pytest tests/\n"
    )
    assert avw.find_disabled_jobs(text) == []


def test_does_not_flag_job_with_no_if_at_all():
    """ジョブレベルの`if:`自体が存在しない通常のジョブは検知対象に
    ならない(誤検知しない)。"""
    text = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: step1\n"
        "        run: pytest tests/\n"
    )
    assert avw.find_disabled_jobs(text) == []


def test_battery_detects_job_level_if_false_regression(monkeypatch):
    """[自己レッドチームの固定] main()レベルでも、ジョブ丸ごと無効化が
    正しくFAILとして報告されることを、一時ディレクトリ上の最小再現
    ワークフローで固定する。"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        wf_dir = Path(td) / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "sabotaged.yml").write_text(
            "jobs:\n"
            "  verify_ataraxia:\n"
            "    if: false\n"
            "    steps:\n"
            "      - name: step1\n"
            "        run: pytest tests/\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(avw, "ROOT", Path(td))
        monkeypatch.setattr(avw, "TARGET_WORKFLOW_DIR", wf_dir)
        try:
            avw.main()
            assert False, "FAILするはずのmain()がsys.exit(1)しなかった"
        except SystemExit as e:
            assert e.code == 1


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
