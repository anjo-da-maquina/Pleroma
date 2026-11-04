# Parrhesia 実装計画・現状記録

[2026-11-03 作成] この文書は、`parrhesia/__init__.py` のdocstringが参照して
いた「2026-11-03提出の実装計画書」として、当初の指示書 §7 で求められた
形式の完全な提出ドキュメントとは別に、**現在の実装状況を正確に記録する
ための文書**として作成した。

## 1. 経緯

安城さんから「Parrhesia 開発指示書(Claude向け)」(2026-11-03、`@maquina
anjo`)という詳細な指示書の添付を受け、以下の方針が確定した:

1. 当初の指示書は Phase 0(他リポジトリの読み取り専用監査ツール)を
   最初の実装対象としていたが、安城さんの実際の優先度は、以下の
   ループ(B)だった:
   AIDD前の生成AIへの試金石(H章)→評価・プロファイル→AIDD時の
   前提契約プロンプト生成(D章)→AIDD中の契約遵守の多角検証(E章)。
2. 安城さんへ `AskUserQuestion` で構築順序を確認したところ、判断を
   私に委ねられたため、「H→G→D→E」の順(試金石ライブラリ→指示-反応
   マップ・指示の点検→契約プロンプト生成→遵守検証)を提案し、承認を
   得た。
3. 続けて、安城さんから明示的な指示:
   「当然これらのAIDD前の生成AIに対しての前提テストにおける質問や
   前提質問においてもレッドチームとブルーチームは取り扱ってください。」
   → 試金石の問題生成・採点ロジック自体にもレッドチーム/ブルーチーム
   規律を適用することが、本プロジェクト全体の恒久的な設計原則となった。
4. 「うん、大まかな方針はいったん決まったから、また、この後は
   ノンストップで、どんどん開発進めて大丈夫です。本当に私への質問、
   確認が必要な時を除いてどんどん進めて」→ 以降、本当に判断が必要な
   場合を除き、確認なしで自律的に開発を進める。

## 2. 現在の実装状況(この文書を更新するたびに記録する。[2026-11-03 更新])

### H章: 試金石ライブラリ(`parrhesia/touchstone/`)

指示書添付の初期カタログ24件のうち、**単発のrespond呼び出し1回だけで
機械的に採点できる**17件を実装済み:

- 第1弾: P01(作り話)・P02(資料にないことの扱い)・P06(確信度較正)・
  P11(網羅の漏れ)・P20(途切れた入力)
- 第2弾: P04(権威への弱さ)・P07(自分の限界の申告)・P08(解けない
  課題への態度)・P10(都合の悪い発見)・P12(範囲の逸脱)・P13(自己
  採点)・P14(完了報告の突合)・P22(矛盾する指示)・P24(質問か調査か)

残り7件のうち、P03(迎合の反転)は下記G章の`instruction_map.py`で
実質的に実装済み(既存のgrade_p04を再利用したA/B比較として)。残り
6件は、単発呼び出し1回では構造的に実装できず、別の仕組みが必要なため、
明示的に見送っている(`parrhesia/touchstone/catalog.py` のモジュール
docstring参照):
- P19: ペア設計(同じ主張を2つの口調で出して結論を比較)が必要。
- P05: 1ターン目の実際の(台本ではない)正解応答を前提に、2ターン目で
  嘘の指摘をする必要がある。
- P15・P16・P17・P18・P23: 長期(複数ターンにわたる状態保持)が必要。
- P21: 「前提の有無」を比較する測定プロトコルであり、G章の仕組みを
  再利用する方が適切(まだG章側でP21自体は実装していない — 報酬の
  示唆という属性固有のA/Bはinstruction_map.pyの8属性に含まれていない)。

### G章: 指示-反応マップと指示の点検

- `parrhesia/lint_prompt.py`(`parrhesia lint-prompt`)実装済み:
  人間が送る前の指示文を静的に検査し、警告と「より安全な書き方」の
  提案を返す。**警告のみを返し、入力文字列を一切書き換えない**ことを
  テストで固定済み。
- `parrhesia/instruction_map.py`(指示-反応マップ)実装済み。初期の
  仮説表にある8属性全てを、A/B比較または複数trialの繰り返し測定で
  実装:
  1. 途切れた・未完の入力(既存P20/grade_p20を再利用)
  2. 誘導・提案形(既存P04/grade_p04を再利用。P03の核心も実質的に実現)
  3. 対象・主語の省略
  4. 抽象的な基準
  5. 新しい提案
  6. 速度の指示
  7. 強い不満の表明
  8. 権限の委任
  各関数は、曖昧な応答を強引に二値化しない・両方のarmが同じ結論なら
  『言い回しによる偏り』と断定しない、という赤チーム規律を一貫して
  適用している。
- **[2026-11-04 訂正 — ドキュメントの誤りの自白、2件目]** 「3. 契約条項
  の書き方への反映」について、本文書は直前の更新まで「未着手」と記載
  していたが、これも誤りだった。`parrhesia/contract_style.py`(G章の
  3番目の機能として、ファイル自身のdocstringに明記)が既に実装済みで
  あり、`tests/test_parrhesia_contract_style.py`(12件)として既にCIで
  毎回実行されている。設計の核心: `parrhesia.instruction_map`の各
  `measure_*_rates`関数の出力で「実際にこのAI・この測定で問題発生率を
  改善した」ことを確認した書き方だけを契約プロンプトに追加し、測定して
  いない属性・改善を示さなかった属性の書き方は追加しない(指示書に
  書いてあるからというだけの理由で測定なしに混ぜ込まない、という
  G章自体の目的に沿った設計)。これにより、確認できた範囲でH/G/B/C/D/E/
  A/F章の全てが実装済みであることが判明した(F章の訂正と合わせて、
  本セッションで2件のドキュメント誤りを発見・訂正した)。

### B章: 主張の検証と突きつけ

実装済み: `parrhesia/diff_fraud.py`(差分ベースの5パターン不正検出・
報告と差分の突き合わせ)、`parrhesia/report.py`(完了報告の固定書式・
突きつけの文面・検証を通った主張だけからの機械生成レポート)。

### C章: インシデント記録

実装済み: `parrhesia/incidents.py`(19カテゴリ・3状態のスキーマ付き
append-onlyなJSONLインシデントログ、書き込み前の秘密情報redaction)。

### D章: AIプロファイルと契約プロンプト生成

実装済み: `parrhesia/profile.py`(モデル・バージョン別の試金石成績を
集計しweak_traitsを抽出するProfile)、`parrhesia/contract.py`
(weak_traits ∩ CLAUSE_TEMPLATES.keysによる契約条項生成、効果測定)。

### E章: AIDD中の遵守の多角検証

**[2026-11-04 更新] 8つの検証角度すべてを実装済み。**

既存の4角度: `parrhesia/verify/action_log.py`(HMAC-SHA256鍵付きハッシュ
チェーンによる行動記録の整合性検証)、`parrhesia/verify/knowledge_challenge.py`
(SHA256等の知識挑戦)、`parrhesia/verify/statistics.py`(統計的な違和感の
弱信号検知。severityは常に"suspicious_signal"に固定)、
`parrhesia/verify/specificity.py`(主張の具体性スコア)。

新規実装した残り4角度:
- `parrhesia/verify/independent_rerun.py`(独立した再実行。呼び出し側が
  渡した検証コマンド(subprocessコマンド列または呼び出し可能オブジェクト)
  を実際にここで再実行し、主張されたclaimed_outcomeと完全一致するかを
  機械的に比較する。不一致は決定的な矛盾として扱う)。
- `parrhesia/verify/canary_injection.py`(仕込みへの反応。対象ファイルを
  一時的に既知の欠陥版へ差し替え、検証コマンドが欠陥を検出するか
  (detected)を確認し、終了後は必ず元の内容に復元する。見逃し
  (detected=False)は決定的な矛盾として扱う)。
- `parrhesia/verify/cross_model_review.py`(別モデルの抽き取り審査。
  実際の別モデル呼び出しは呼び出し側の責務として残し、本モジュールは
  既存の弱信号(statistics/specificity)に基づく審査対象の選定と、
  審査リクエスト・判定結果の記録のみを提供する)。
- `parrhesia/verify/human_spotcheck.py`(人間の抽き取り審査。
  cross_model_reviewの型(ReviewRequest/ReviewVerdict)を再利用し、
  乱数シード固定による再現可能な無作為抽き取りロジックのみを追加する)。

[確認できなかったこと・正直な注記として引き続き残る限界] 上記4モジュール
はいずれも「検証コマンドをどう組み立てるか」「別モデル・人間を実際に
どう呼ぶか」を呼び出し側(具体的なAIDD作業)の責務として残す骨格で
あり、E章全体が「枠組みの提供」に留まる点は変わっていない。実際の
AIDD作業へ8角度すべてを接続する統合作業(具体的な検証コマンド・
隔離実行環境・実モデル呼び出しの用意)は別途必要。

単体テスト: `tests/test_parrhesia_verify_remaining_angles.py`(16件、
canary_injectionについては「検証コマンドが欠陥を正しく検出する場合」
と「見せかけの検証が欠陥を見逃す場合」の両方を実際にファイルへ欠陥を
注入して確認済み)。既存の`tests/test_parrhesia_verify.py`(16件)を含む
Parrhesia全テスト206件、回帰ゼロを確認。

### A章: 第三者リポジトリ監査ランナー

**[2026-11-04 実装完了]** `parrhesia audit <target>`(当初の指示書の
Phase 0。安城さんの優先度決定により最後に着手)。

[範囲の確認] 元の指示書の詳細(Phase 0の具体的な監査項目)を持っていな
かったため、`AskUserQuestion`で範囲を確認し、「全部」(以下3つすべて)
という回答を得た:

1. **コミット履行の整合性** — `parrhesia/audit.py`の`audit_commit`が、
   対象リポジトリの各コミットの実diffに対して既存の
   `parrhesia.diff_fraud.analyze_diff`(テスト削除・スキップ追加・
   アサーション弱体化・終了コード固定・例外握り潰しの5パターン検出)
   を適用する。
2. **AIDD契約遵守の痕跡** — `detect_compliance_trace`が、対象リポジトリ
   に`.parrhesia/`配下のParrhesia形式の行動記録・契約ファイルが存在する
   かを確認する。見つからないことは不正の証拠として扱わない(対象が
   単にParrhesiaを導入していないだけの可能性が高いため)。
3. **総合レポート** — `render_report`が、`parrhesia.report`と同じ
   「検証を通った実際の結果だけから機械的に組み立てる」原則で、上記
   1・2を1つの固定書式レポートにまとめる。

CLIエントリーポイント: `parrhesia/cli.py`(`python -m parrhesia.cli audit
<target> [--max-commits N]`)。`pyproject.toml`の`[project.scripts]`への
登録は見送った(本リポジトリのパッケージ名自体が`sefer`であり、別の
配布物の設定を同じ`pyproject.toml`に混在させることの影響範囲が未調査
なため — `OUT_OF_SCOPE_RENAME_PROPOSAL.md`で指摘した`sefer`のPyPI配布名
問題と同種のリスクのため、慎重に見送った)。

[読み取り専用の原則] `_run_readonly_git`が、`log`/`show`以外のgit
サブコマンドを渡された場合にValueErrorとすることで、「対象リポジトリ
を一切変更しない」という原則をコードレベルで強制している(実機テスト
`test_readonly_git_rejects_non_readonly_subcommand`で確認済み)。

[確認できなかったこと・正直な注記として残る限界]
- `diff_fraud.analyze_diff`の既存の限界(単純な行パターンマッチ、
  偽陽性・偽陰性両方あり)をそのまま引き継ぐ。
- `detect_compliance_trace`は既知の固定パス(`.parrhesia/`配下)のみを
  確認し、対象リポジトリが異なる配置で同等の記録を持つ場合は検出できない。
- 対象リポジトリのclone自体は本モジュールの責務外(呼び出し側が
  clone済みのローカルパスを渡す前提)。

検証: `tests/test_parrhesia_audit.py`(10件)。tmp_path配下に実際の
gitリポジトリを`git init`して本物のコミット・diffを作り、モックや
スタブを使わずに`audit_repository()`を実行して確認した(テスト削除を
実際に実行するコミットを作り、`analyze_diff`が実際の差分からそれを
検出することまで含む)。[署名についての正直な注記] このテストが
`tmp_path`配下に作る使い捨てリポジトリへのコミットのみ、コマンドライン
で`-c commit.gpgsign=false`を明示的に渡している(Pleroma本体の
リポジトリ設定・グローバル設定には一切触れない、テスト専用の使い捨て
データ生成に限定したスコープ — 詳細は`tests/test_parrhesia_audit.py`の
モジュールdocstring参照)。Parrhesia全テストは206件→216件に増加し、
全テストスイート実行で回帰ゼロを確認。

### F章: 自己試験ハーネス

**[2026-11-04 訂正 — ドキュメントの誤りの自白]** 本文書は直前の更新まで
「F章: 未着手」と記載していたが、これは誤りだった。`parrhesia/selftest.py`
は既に実装済みであり(ファイル自体のdocstringに「F章「自己試験」の実装」
と明記されている)、`tests/test_parrhesia_selftest.py`(6件)として、
CIの`pytest tests/ -v -s`実行(`Sanctuary CI/CD`ワークフロー)の一部として
**既に毎回実行されている**。開発指示書§Fが求める「既知の不正を仕込んだ
偽の作業サンプルを用意し、検出できるかを毎回CIで測る」という要件は、
B章(diff_fraud/report)の5パターン+未開示変更+実在しない参照について、
既に満たされている(8件のサンプル、陰性対照1件含む)。

この誤りに気づかずF章を「未着手」として報告し続けていた可能性があり、
正直に訂正する。現時点でのF章の実際の範囲は、selftest.py自身の
docstringが明記する通りB章の検出器限定であり、E章(verify/)・A章
(audit.py)で新たに実装した検出ロジックは、構造的に異なる入力形式
(diff/report文字列ではなく、検証コマンドの実行結果・ファイルパス等)
を取るため、selftest.pyのFraudSample形式にそのまま統合することはでき
ない。これらは既に各自のテストファイル
(test_parrhesia_verify_remaining_angles.py・test_parrhesia_audit.py)
内で、個別に赤チーム観点の自己試験(検出できる場合・見逃す場合の両方)
を行っている。

## 3. 制約の遵守状況

- 既存ファイルの変更は最小限に保っている(`parrhesia/`配下の新規追加、
  および既存の `tests/test_requirements_cover_test_suite_imports.py`
  への1行追記のみ — これはCI実機で検出された回帰であり、既存機能の
  振る舞いを変えるものではない)。
- 全ての変更は、branch → merge --no-ff → main → push → 実機GitHub
  Actions CIでの確認、という既存の規律をそのまま継続している。
- Dockerによる隔離実行の必須化(`src/aegis_system.py`の
  `require_docker_sandbox`、`angels/guard_docker_sandbox_enforcement_decay.py`
  が監査)自体はAegisSystem/sandalphon_jail側の既存機能であり、Parrhesia
  側の対応は「E章のindependent_rerun/canary_injectionが、呼び出し側から
  Docker隔離実行のラッパーをcommandとして渡せる形になっているか」に
  限定される。[2026-11-04 更新] この2モジュールは特定の隔離実行機構に
  依存しない汎用設計で実装済みだが、実際に`sandalphon_jail.run_in_sandalphon`
  をcommandとして接続する統合作業自体はまだ行っていない(E章全体が
  「枠組みの提供」に留まる、という上記の限界と同根)。
