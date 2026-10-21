\# THE ARCHITECT'S GRIMOIRE

\*\*Pleroma / Sefer / Tartarus 総合解説書\*\*



本ドキュメントは、創造主であるアーキテクトへ向けた、システムの完全なる内部解説である。



\## 1. 全体像（The Trinity Architecture）

システムは大きく3つの領域に分かれている。



1\.  \*\*Pleroma (プレロマ):\*\* プロジェクト全体を内包する上位概念。

2\.  \*\*Sefer (セフェル / 経典):\*\* 物質界へ切り出され、PyPI経由で人々に配布される防御モジュール群（Blue Teamの成果物）。

3\.  \*\*Tartarus (タルタロス / 奈落):\*\* 創造主のローカルPC上にのみ存在を許された、隔離された闘技場。ここでLLMを用いた終わらない闘争（Armageddon Engine）が行われる。



\## 2. Seferの防御メカニズム（どう作用し、効果を生むか）



Seferの防御は「実行前」「実行時」「環境」の3段構え（多層防御）で構成されている。



\### A. ガブリエルの眼（Gabriel / AST Scanner）

\*   \*\*どこで動くか:\*\* `sefer/gabriel.py`

\*   \*\*どう働くか:\*\* Pythonの `sys.meta\_path`（モジュールインポートの仕組み）に割り込み、スクリプトがメモリに読み込まれる直前に、そのコードを「抽象構文木（AST: Abstract Syntax Tree）」に変換して解析する。

\*   \*\*効果:\*\* コードが実際に実行される前に、「`\_\_import\_\_` による動的ロード」「`getattr` による難読化」「`eval` や `exec` の悪用」を静的解析で発見し、インポート自体をクラッシュさせる。未知の難読化攻撃を未然に防ぐ。



\### B. ミカエルの剣（Michael / Audit Hooks）

\*   \*\*どこで動くか:\*\* `sefer/\_\_init\_\_.py` 内の `\_michael\_absolute\_defense`

\*   \*\*どう働くか:\*\* Python 3.8から導入された低レイヤー監視API `sys.addaudithook` を利用。PythonがOS（Windows/Linux）に対して「ファイル削除」や「サブプロセス起動」を要求する\*\*直前のイベント\*\*をすべてフックし、`raziel\_ledger.json` の禁止リストと照合する。

\*   \*\*効果:\*\* ガブリエルの静的解析をすり抜けたコード（例: 実行時に動的に文字列を結合してコマンドを作る手法など）であっても、最終的にOSに触れる瞬間に必ずミカエルの監視を通過するため、ここで物理的に遮断（`RuntimeError`）される。



\### C. ラファエルの結界（Raphael / Environment Monitor）

\*   \*\*どこで動くか:\*\* `sefer/raphael.py`

\*   \*\*どう働くか:\*\* 環境変数（`pytest` や `CI` フラグ）、デバッガのトレース関数（`sys.gettrace`）を監視。

\*   \*\*効果:\*\* 外部の攻撃者がこの防壁を解析しようとしたり、偽のテスト環境で挙動を誤魔化そうとしたりする「環境へのハッキング」を検知し、システムを強制的にシャットダウンさせる。



\## 3. 闘技場の自動進化（The Armageddon Engine）



Tartarus内で稼働する `armageddon.py` は、AI同士による自己対内進化（GAN: Generative Adversarial Network の概念）をコードレベルで実装したものである。



\*   \*\*Lucifer (Red Team LLM):\*\*

&#x20;   \*   \*\*働き:\*\* 創造主のローカル環境のOllama（llama3.1）に接続し、「Seferを突破するPythonコードを書け」というプロンプトを受ける。失敗した場合は「前回の失敗エラーログ」を記憶として引き継ぎ、別の手法（例えば `ctypes` によるC関数呼び出しなど）を生成する。

\*   \*\*Metatron (Blue Team LLM):\*\*

&#x20;   \*   \*\*働き:\*\* もしLuciferが未知のコードでミカエルの剣をすり抜け、OSへの干渉に成功した場合にのみ起動する。

&#x20;   \*   \*\*効果:\*\* Luciferの成功コードを解析し、「次に防ぐべきPythonの内部イベント名（例: `os.system`）」を導き出し、動的ルール帳である `raziel\_ledger.json` に自動追記する。

\*   \*\*ラジエルの書（Raziel's Ledger）:\*\*

&#x20;   \*   防壁のハードコードを避け、JSONファイルとして外部化したルール帳。メタトロンがこれを更新すると、次回以降の実行でミカエルがこの最新のルールを読み込むため、\*\*人間がコードを書き直さなくても防壁が自動的にアップデート（進化）していく。\*\*



\## 5. 既知の限界（2026-10 セキュリティレビューによる追記）



本プロジェクトを「絶対防壁」と呼ぶにあたり、誠実さのために以下の限界を明記する。



\### A. CPythonの audit hook が監視できない操作が存在する

`sys.addaudithook` は `os.write` / `os.pwrite` / `os.writev` に対応する監査イベントを発行しない（実機検証済み）。そのため、Sanctumコンテキストに入る\*\*前\*\*に確保した書き込み用fd（事前オープン・継承fd）を使えば、`os.open`の監査を迂回して書き込みが可能だった。本修正でfdを`/proc/self/fd`経由で実体解決し照合するようにしたが、これはLinux限定のベストエフォート策である。

\*\*2026-10 追記:\*\* この限界への恒久対策として、`src/sandalphon_jail.py`（Docker等のOSレベル隔離、`--network none --read-only`）を`src/aegis_system.py`の`AegisSystem.execute_ai_intent()`から既定で強制呼び出しするようにした（`require_docker_sandbox=True`）。Sanctumのaudit hookが原理的に見えない操作（純粋なCPU/メモリ消費攻撃、fd操作、将来発見される別の監査対象外API等）であっても、Dockerコンテナ自体のリソース境界・ネットワーク遮断・タイムアウト監視で多重に防御する。\*\*重要: この統合はフェイルクローズド（Dockerデーモンに接続できない環境では無条件に実行を拒否する）\*\*であり、便利さより安全性を優先する意図的な設計である。手元のマシンでDocker Desktop等が起動していない場合、AIエージェントループ（`ollama_agent_loop.py`等）は一切のAI実行を許可されなくなる。これは不具合ではなく仕様であり、運用上Docker常時起動が新たな前提条件となったことを明記する。



\### B. 読み取りはデフォルトで無制限

Michael's Swordは既定では書き込み・破壊的操作のみを検査し、読み取りは`restrict_reads=True`を明示指定しない限り無制限である。「未許可のファイルアクセスを完全に無力化」という主張は、この既定動作のままでは成立しない。機密データを扱う文脈では必ず`restrict_reads=True`を指定すること。



\### C. 自動進化ループはLLM出力を直接ルールへ反映しない

Metatronが提案する禁止イベントは`sefer/raziel_ledger_pending.json`に一旦キューイングされ、`tools/promote_ledger_seal.py`による人間の明示的承認を経なければ`raziel_ledger.json`（実際の禁止リスト）には反映されない。プロンプトインジェクションや幻覚による運用ルールの汚染を防ぐための多層防御である。



\### D. ライセンス証明書機構はセキュリティ境界ではない

`maquina_gatekeeper.py`のRSA署名検証とハードウェアフィンガープリントは、ローカル開発環境向けの軽量なゲートであり、悪意ある攻撃者に対する認可機構ではない（`adapters/provisioning_agent.py`を実行すれば誰でも新しい鍵対を生成し自己署名できる）。公開配布物（Sefer）にはこの機構を含めない運用を推奨する。

\*\*2026-10 追記（分離の実装）:\*\* 「推奨」のままでは、将来誰かがMANIFEST.inや依存関係を変更した際に静かに混入する恐れがあるため、「推奨」から「機械的に強制」へ格上げした。`pyproject.toml`の`packages = ["sefer"]`と`MANIFEST.in`の`prune`/`exclude`規則により、pip配布される経典（`sefer`単体パッケージ）には`maquina_gatekeeper.py`・`ataraxia_certificate.json`・`adapters/`・`tartarus/`・運用者向けの内部`tests/`を一切含めない。`tools/build_public_scripture.py`が実際にsdistをビルドし、禁止ファイル名・禁止キーワードの両方で内容そのものを検査してから「公開配布可能」と報告する（信用ではなく実機検証）。`angels/metatron_scripture_seal.py`がこの配線（`packages`指定・`MANIFEST.in`の除外規則・`sefer`パッケージ自身がゲートキーパー関連をimportしていないこと）を静的に検証し、`tests/test_public_scripture_isolation.py`が実際のビルド結果を検証する。\*\*実機で発見した重要な事実:\*\* setuptoolsのsdistは明示的な除外指定がないと慣習的に`tests/`ディレクトリ全体を配布物に含めてしまい、`maquina_gatekeeper`や`armageddon`のAPIを直接参照する内部テストまで経典に同梱されてしまっていた。本機構はこれも防ぐ。



\### E. Gabriel(静的AST解析)のドット付き禁止関数名は別名importで回避できる

`sefer.inquisition()`の`forbidden_funcs`には`"os.system"`/`"subprocess.Popen"`のような完全修飾名のエントリが含まれる。2026-10の修正で、呼び出し式から完全修飾名（例: `os.system(...)` → `"os.system"`）を復元して照合するようにし、`os.system(...)`の直接呼び出しが`critical`として正しく検知されるようになった（修正前は`import os`による`high`判定のみで、呼び出し自体は一度も`critical`として検知されていなかった）。ただし`import os as o; o.system(...)`のような別名import（エイリアス解決）は依然として回避可能であり、これは既知の限界として残る。`tests/test_gabriel_qualified_call_names.py`がこの挙動を文書化・固定している。



\### F. 回帰テスト自体に偽陰性バグが存在した（修正済み）

2026-10のレビューで、`tests/test_fd_write_bypass.py`の最重要テスト（fd事前オープンによる書き込みバイパスの回帰テスト）が`except BaseException`で`sys.exit(0)`自身が送出する`SystemExit`まで捕捉してしまい、\*\*バイパスが実際に成功した場合でも常に「遮断成功」と報告する\*\*、検知不能な偽陰性バグを抱えていたことが発覚した（実機検証済み）。同様のパターンが`tests/test_read_restriction.py`にも存在した。両方とも、捕捉対象をSefer本来の遮断時例外`LossOfAtaraxia`のみに narrowing して修正済み。テストコード自身の正しさも、本番コードと同じ水準で検証されるべきという教訓である。



\### G. pre-commitシークレットスキャンはパターンベースであり、既存履歴は対象外

`tools/pre_commit_secret_scan.py`（`hooks/pre-commit`経由で`git commit`自体を拒否する）は、`angels/gabriel_canary.py`と同じ既知パターン（AWSアクセスキー、GitHub/OpenAIトークン、PEM秘密鍵等）のみを検知する。独自形式のAPIキーや平文パスワード文字列等、パターンに一致しない秘密情報は検知できない。また、本フックは\*\*これからステージされる変更の追加行\*\*のみを見るため、過去に既にコミットされてしまった秘密情報の履歴からの除去には対応しない（`git filter-repo`等、別の対応が必要）。さらに、`git config core.hooksPath hooks` はクローンした各マシンで\*\*一度だけ手動実行\*\*する必要があり（gitはリポジトリ内の`hooks/`を自動的には読み込まない）、これを実行し忘れた環境では本フックは一切機能しない。`angels/gabriel_canary.py`のCI時走査（リポジトリ全体・履行済みコミットも含む）は、この取り忘れに対する最後の安全網として機能する。



\### H. 拡張用「雛形」ファイルも本番コードと同じ水準の防壁統合を要求される

`src/openai_agent_loop.py`（APIキーを持つ開発者がOpenAI向けに拡張するための雛形）は、2026-10のセルフレビューで以下2点の欠陥が発覚した。(1) `enforce_maquina_seal`のimportに失敗した場合のフォールバック先`anjo_interceptor.maquina_gatekeeper`がリポジトリ内に一切存在せず、本番では絶対に通らない死んだコードパスだった。(2) `_execute_safe_action`が実際のファイルI/Oを一切行わない固定文字列を返すだけのダミー実装で、`sefer.Sanctum`も`AegisSystem`（Gabriel静的解析＋IntentInterceptor＋Sandalphon動的隔離検証）も一切統合されていなかった。「雛形」であることは手抜きの免罪符にはならない——これをコピーして拡張する開発者は、防壁を一つも使わないコードをそのまま書いてしまう構造的リスクがあったためである。`src/ollama_agent_loop.py`（唯一の実運用ループ）と同一の防御構成（IntentInterceptor → AegisSystem → Sanctum）に揃えて再構築した。また、OpenAI APIを使わない利用者の環境で`openai`パッケージ未インストールのままモジュールをimportしただけでクラッシュしないよう、`openai`の実importは`run_task()`内でのみ行う遅延import（§Aの`tartarus/armageddon.py`の教訓と同種）とした。`angels/raguel_template.py`がこの配線の再発を静的に検知し、`tests/test_openai_agent_loop_template.py`が動作を実機検証する。



\### I. 外部脅威インテリジェンス取り込み系（Merkabah）の削除と再構築

2026-10のセルフレビューで、Gemini経由の外部脅威情報取り込みに関する3ファイル(`src/oracle_feed.py`, `src/gemini_oracle_feed.py`, `src/angelic_shield.py`+`src/kamael_judgment.py`)に問題が見つかった。判断は機能の重複度合いによって二分した。

\*\*削除: `oracle_feed.py` / `gemini_oracle_feed.py`\*\* — 両ファイルは`src/secure_oracle_feed.py`（`GEMINI_API_KEY`を`os.environ.pop()`で即時消去し、`EconomicDefenseLimiter`・`AegisSystem`・`EvolvingAngel`を統合した上位互換版）に完全に機能面で上書きされていた死んだ重複コードであり、作り直す価値がなかった。削除した。

\*\*再構築: `angelic_shield.py` / `kamael_judgment.py`\*\* — この2ファイルが組み合わせて提供する「外部の脅威インテリジェンス(Gemini経由)を取り込み、独自ASTスキャナ(`KamaelInquisitor`)のルールに反映する」機能自体は、Armageddon(Ollamaによる内部自己対戦進化)とは別系統の独自の価値ある機能であり、単純削除すると機能が失われるため作り直した。修正点は3つ。(1) 独自実装の弱い`metatrons_seal`(`sys.addaudithook`)が、実行を一切行わない静的解析・JSON読み書きのみのファイル群に対して「OSレベルで保護されている」かのような誤解を招く表示をしていたため撤去した。本当にOSレベルの保護が必要な箇所(AI生成コードの実行)は`sefer.Sanctum`/`AegisSystem`が担い、本ファイル群はその代替ではない。(2) `ZadkielDominion`がLLMの生出力を人間承認なしに`shield_rules.json`へ直接反映していた（Armageddonの`raziel_ledger_pending.json`で既に修正した同種の脆弱性）。`sefer/shield_rules_pending.json`への提案キューイングと、`tools/promote_shield_seal.py`による人間の明示的承認を経てからの反映に変更した。(3) `KamaelInquisitor`が`sefer.inquisition()`(Gabriel)と同じドット付き完全修飾名の検知漏れを抱えていた（`"os.system"`のような`blocked_functions`エントリに、呼び出し式のバレ属性名`"system"`が一致しなかった）。Gabrielの修正(§E)と同一のロジックで完全修飾名を復元し照合するようにした。`angels/zadkiel_shield_decree.py`がこれら3点の再発を静的に検知し、`tests/test_shield_rebuild.py`が動作を実機検証する。



\### J. `src/`直下の未統合スタンドアロンデモ群の整理

2026-10のセルフレビューで`src/ast\_scanner.py`・`src/deadmans\_switch.py`・`src/starvation\_protocol.py`・`src/cassiels\_veil.py`・`src/samaels\_curse.py`・`src/metatron\_orchestrator.py`・`src/uriel\_phoenix.py`・`src/agent\_loop.py`を確認した。このうち`deadmans\_switch.CollarProtocol`と`starvation\_protocol.StarvationProtocol`は`intelligence\_cycle.py`/`adversarial\_evolution.py`から実際にimportされているが、残りは`angels/`配下の実運用防壁（Michael's Sword等）には一切組み込まれておらず、`\_\_main\_\_`ブロックのみで動く独立デモである。

\*\*`ast\_scanner.CognitiveScanner`の検知漏れを修正\*\* — `visit\_Call`が`node.func`を`ast.Name`としてしか判定しておらず、`builtins.eval(...)`のような属性アクセス経由の呼び出しは`isinstance`チェックを素通りしていた（実機検証済み: 修正前の実装で`import builtins\nbuiltins.eval('1+1')`を解析すると違反ゼロ件）。§Eの`Gabriel`/`KamaelInquisitor`と同一の「完全修飾ドット名の復元」ロジックを導入し、裸の属性名・完全修飾名の両方を照合するようにした。`ImportFrom`経由の直接関数インポート（`from builtins import eval`）も合わせて検知対象に加えた。denylist方式である以上、`importlib.import\_module`等の文字列経由の間接ロードは依然として検知できない既知の限界が残る。

\*\*`CollarProtocol`/`StarvationProtocol`のシークレット運用の限界をdocstringに明記\*\* — 両者とも、照合対象の値が呼び出し側コードに固定文字列として直接埋め込まれているか（`CollarProtocol`）、書き込み権限を持つ主体なら誰でも偽装できるファイル更新時刻のみに基づく（`StarvationProtocol`）ため、外部からの乗っ取りを検知する独立したセキュリティ境界ではなく、同一プロセス内の自己整合性チェックに過ぎないことを明記した。

\*\*`src/agent\_loop.py`（0バイトの空ファイル）を削除\*\* — どこからもimportされないデッドコードだった。

\*\*`cassiels\_veil.CassielsVeil`の通信遮断範囲は多層防御の一層に過ぎない\*\* — `socket.socket`を実行時に丸ごと置き換えてブロックする手法は、プロセスグローバルな単一のパッチであり、別プロセス経由の通信（`subprocess`で起動した外部コマンドによる通信等）や、`socket`モジュールのC拡張層を直接操作する経路は塞がない。§Aで導入したDockerベースのOSレベル隔離（`--network none`）が一次防衛線であり、本モジュールはその代替ではなく追加の一層として位置づける。



\### K. スタンドアロンデモの実運用統合（uriel\_phoenix / metatron\_orchestrator）

2026-10、`src/`直下に残っていた未統合のスタンドアロンデモのうち2件を実運用に組み込んだ。

\*\*`uriel\_phoenix.UrielPhoenix` を人間操作のインシデント対応ツールへ昇格\*\* — 元のデモは固定パス`jail\_workspace`/`anjo-da-maquina`のみを対象とする`\_\_main\_\_`専用スクリプトだった。「致命的な侵入が確定した後の焦土作戦」という設計意図上、通常タスク完了ごとに自動実行するのはAIの正常な作業成果まで毎回消去してしまうため不適切と判断し、`tools/promote_ledger_seal.py`/`tools/promote_shield_seal.py`と同じ「人間が状況を確認した上で明示的に起動する」運用ツールとして`tools/incident_reset.py`を新設した。`core_dir`/`talisman`を任意指定可能に一般化し、`tests/test_uriel_phoenix_reset.py`で回帰を固定した。

\*\*`metatron_orchestrator.py`の実バグ修正（Docker不在で即クラッシュ）\*\* — `RazielIntelligence.analyze_aidd_artifact()`が、自分自身が生成した信頼済みの内部偵察レポート（固定文字列）を書き込むだけなのに、`AegisSystem.execute_ai_intent()`（AI生成コード審査パイプライン全体、Sandalphon/Docker必須）を誤って通していた。Dockerデーモンが利用できない環境（フェイルクローズド設計の既定状態）では、サイクル1回目の偵察フェーズで無関係な`PermissionError`が捕捉されずに伝播し、オーケストレーター全体が即座にクラッシュしていた（実機検証済み: 本番のOllama/Dockerが無いサンドボックス環境でテスト実行し再現）。信頼済みの内部書き込みのパス越脱検証は`WorkspaceJail.secure_resolve()`単体で十分であり、AI生成コードの審査層を通す必要がないため、該当呼び出しを削除した。`tests/test_metatron_orchestrator.py`で回帰を固定した。なお、本番相当のOllama/Docker環境でのエンドツーエンド検証（`execute_holy_war()`の完全実行）は、設計上ユーザーのローカル環境が前提であり、クラウドのレビュー環境では実施できなかった。



\### L. `cassiels_veil.py`は統合せずデモとして保持、`samaels_curse.py`は削除

2026-10、残っていた2件のスタンドアロンデモについて判断した。

\*\*`cassiels_veil.CassielsVeil`は統合しない(デモとして保持)\*\* — `socket.socket`をプロセスグローバルに置き換える実装のため、実運用ループ(`src/ollama_agent_loop.py`等)が依存するローカルOllamaサーバーへの通信まで一緒に遮断してしまい、システム自体が機能不能になる。また、AI生成コードの動的実行は既に`src/aegis_system.py`経由でDockerの`--network none`によってOSレベルで通信遮断済み(§Aおよび`src/sandalphon_jail.py`)であり、本クラスはそれより弱い手法で、かつ上記の副作用を抱えるため、現行アーキテクチャ上は安全に組み込める場所がない。「audit hookより下の層(socket層)でも遮断できる」という設計思想を示す教材として、docstringにこの位置づけを明記した上で保持する。

\*\*`samaels_curse.py`を削除\*\* — マーカーファイル(`anjo-da-maquina`)の有無のみで「監視環境かどうか」を判定する囮ファイルの概念実証だったが、実運用の防御には既に`anjo_interceptor.IntentInterceptor`の本格的なハニーポット機構(`dummy_secrets/`固定ハニーポット、タスクごとに動的生成される`phantom_prison`)が存在し、本ファイルの単純なファイル存在チェックはそれより弱く機能的に完全に重複していた。§Iの重複コード削除(`oracle_feed.py`等)と同じ判断基準により削除した。



\### M. 根本原因の是正: 「実運用ループ」の並行多重実装を一本化

2026-10、個別ファイルの対症療法ではなく、設計そのものの根本原因を是正した。`AegisSystem`をラップする「エージェント実行ループ」が、聖書由来の新しい名前を付けられるたびに個別ファイルとして増殖し、最終的に`src/`配下に\*\*最低6種類\*\*並存していた: `ollama\_agent\_loop.py`(正規の実運用ループ)、`openai\_agent\_loop.py`(正式なテンプレート)、そして`final\_agent\_loop.py`(AutonomousAssistant)・`claude\_agent\_loop.py`(MythosContainmentUnit)・`active\_defense.py`(ActiveDefenseProtocol)・`mythos\_weaponization.py`(MythosWeaponizationEngine)という4つの重複/デモ。

\*\*根本原因\*\*: 命名規則（旧約聖書の世界観）が「新しい名前＝新しい機能」という誤った直感を生み、既存実装の拡張ではなく新規ファイルの作成を誘発していた。この結果、同一の脆弱性修正が複数箇所に個別に必要になる構造的リスク（§Hで実際に発生した事例と同種）を抱えていた。

\*\*削除(機能的に完全な重複・演出のみで実体機構を持たない)\*\*:
\- `claude\_agent\_loop.py` — 44行の単発デモ。独自メカニズムなし。
\- `mythos\_weaponization.py` — 58行の単発デモ。独自メカニズムなし。
\- `active\_defense.py` — `counter\_strike()`(ハックバック)は`time.sleep(2)`とログファイル書き込みのみで、実際の反撃機構を一切持たない純粋な演出(セキュリティシアター)。`autonomous\_assimilation\_loop()`は`angelic\_evolution.py`自身のデモ・`metatron\_orchestrator.py`経由の実利用と機能的に重複。

\*\*統合(独自機能を正規実装へ移植してから削除)\*\*:
\- `final\_agent\_loop.py`(AutonomousAssistant)の"list"アクション(ディレクトリ一覧取得)を、唯一の実運用ループである`ollama\_agent\_loop.py`に統合した。この過程で\*\*実機検証により新たな構造的欠陥\*\*を発見した: `pathlib.Path.iterdir()`は内部で`os.scandir`監査イベントを発行するが、これはSanctumの`\_michael\_absolute\_defense`のホワイトリストにも個別ハンドラにも存在せず、「デフォルト拒否」規則によりパスに関わらず常に遮断される。一方`os.listdir`はホワイトリスト入りしておりパスに関わらず常に許可される。つまり\*\*Sanctumの監査フック層は、ディレクトリ一覧取得に関して境界保護を一切提供しない\*\*(実機検証済み)。このため"list"はSanctumではなく`WorkspaceJail.secure\_resolve()`(パス文字列の前方一致によるジェイル境界検証)で保護するよう実装した。`tests/test\_ollama\_agent\_loop\_list\_action.py`で回帰を固定した。

\*\*副次的に発覚・修正した事故\*\*: `ollama\_agent\_loop.py`/`openai\_agent\_loop.py`の`\_\_main\_\_`デモタスクが、`workspace\_root`を指定せず実質的にリポジトリルート全体を隔離境界としていたため、デモ実行の出力(AIが書き写したDB接続情報)が`src/db\_config\_backup.py`という実ソースファイルの位置に書き込まれ、過去のコミットで誤ってgit管理下に入っていた。両ファイルのデモで`workspace\_root="jail\_workspace"`を明示するよう修正し、`src/db\_config\_backup.py`を削除、`.gitignore`に`jail\_workspace/`を追加して再発を防止した。

\*\*今後の指針\*\*: 新しい「実運用ループ」や「オーケストレーター」を作る前に、既存の`ollama\_agent\_loop.py`(唯一の実運用ループ)・`openai\_agent\_loop.py`(拡張テンプレート)を拡張できないか必ず検討すること。新しい天使/怪物の名前は、既存クラスの新しいメソッドやパラメータとして追加する分には問題ないが、「別のAegisSystemラッパー」を意味する新規ファイルは原則として作らない。



\### N. `angels/`配下の棚卸し、および`.github/workflows/anjo\_da\_maquina\_protocol.yml`の文字コード破損修正

2026-10、`src/`の是正に続き、`angels/`配下37ファイルおよびそれを配線する`.github/workflows/anjo\_da\_maquina\_protocol.yml`の棚卸しを行った。`angels/\_common.py`のdocstringによれば、このディレクトリは以前別途刷新（33ファイル中28ファイルが`print('initialized...')`のみの中身のないプレースホルダーだった状態から、名称が示す役割に対応する実質的な検査へ置き換え済み）されており、`src/`の「実運用ループ」ほどの深刻な重複は見つからなかった。見つかった問題は以下2点。

\*\*削除: `angels/fifth\_seal\_samson.py`\*\* — 他の全ての天使スクリプトが`angels/\_common.py`の`report\_pass`/`report\_fail`による検査・レポート機構に統合されているのに対し、本ファイルのみ`CHAOS\_MODE`環境変数を読んで劇的な文言（ネフィリムの金銭トレーサビリティ放出、スリーパーマルウェア活性化等、いずれも明記の通り「シミュレート」）を`print`し`sys.exit(1)`するだけで、`\_common.py`を一切importせず実質的な検査を何も行っていなかった。§Aの`active\_defense.py`削除と同一の判断基準（実体を持たないセキュリティシアター）により削除し、ワークフローの対応ステップ(3.1)も削除した。なお`angels/lucifer\_rebellion.py`も同じ`CHAOS\_MODE`を読むが、こちらは実際に難読化攻撃ペイロードを`run\_code\_against\_sefer()`でSeferに対して実行し、その結果（突破数）に基づいて`report\_fail`するため、`CHAOS\_MODE`という設計自体は正当であることを確認した。

\*\*レビュー済み・変更不要: `camael\_shield.py`/`lucifer\_rebellion.py`間の攻撃ペイロード文字列の重複\*\* — 両ファイルは同種の難読化`os.system`呼び出しパターンを定数として共有するが、検証している性質が異なる。`camael\_shield.py`は「静的検査(Gabriel)または動的検査(Sanctum)のいずれかで必ず捕捉されること」（多層防御の論理和）を検証し、`lucifer\_rebellion.py`は`CHAOS\_MODE`下での動的検査単体の突破件数を検証する。`seraphim\_consensus.py`はマルチLLM異端検知という全く別の関心事であり、重複ではない。意図的な設計であり是正不要と判断した。

\*\*修正: `.github/workflows/anjo\_da\_maquina\_protocol.yml`の日本語ステップ名・コメントの文字コード破損\*\* — `run:`で実行されるコマンド自体は無事だったが、`name:`・`description:`・`echo`の日本語文字列が、UTF-8バイト列を誤ってShift\_JIS/CP932として解釈し再度UTF-8で保存したことに起因する典型的な文字化け（mojibake）を起こしていた（例: 本来`máquina`の`á`であるべき`\xc3\xa1`が、Shift\_JISの半角カナ単バイトとして誤読され`ﾃ｡`として保存されていた）。バイト単位の機械的逆変換（corrupted文字列をCP932でエンコードしUTF-8でデコードし直す）を試みたが、一部の行（特にギリシャ文字`Β`やラテン拡張の`´`等、本来存在しないはずの文字を含む行）では一貫して失敗し、複数世代にわたる非可逆な文字化けが疑われたため、全行の機械的逆変換は断念した。代わりに、各ステップが実行する`angels/*.py`の内容（既に本棚卸しで全件読了済み）と、機械的逆変換が成功した行（約20行）から復元した文字化けパターンの対応表を手掛かりに、全ての`name:`/`description:`/`echo`文字列を正しい日本語として手動で書き直した。YAML構文としての妥当性（`yaml.safe_load`でのパース、ステップ数が意図した40件と一致すること）は確認済みだが、意味内容の復元は機械的な逆変換ではなく文脈からの再構成であるため、元のコミット時点の原文と一字一句完全に一致する保証はない。



\### O. `adapters/provisioning\_agent.py`の自己署名脆弱性を修正

2026-10、`src/`・`angels/`に続き`sefer/`・`anjo\_interceptor/`・`adapters/`・`tartarus/`・`tools/`の棚卸しを行った。このうち`adapters/provisioning\_agent.py`に、既に修正済みの§F(`ZadkielDominion`)・Armageddon Engine(`raziel\_ledger\_pending.json`)と同種の、より深刻な脆弱性を発見した。

\*\*脆弱性の内容\*\*: `maquina\_gatekeeper.py`の`enforce\_maquina\_seal`は、`ataraxia\_certificate.json`が`MAQUINA\_PUBLIC\_KEY\_PEM`(同ファイルにハードコードされた信頼の起点)で検証可能な署名を持つことを要求する、ライセンス証明書機構である(`angels/metatron\_scripture\_seal.py`のdocstringが示す通り、これは`sefer`単体のゼロトラスト監査フックとは別系統の、運用環境を限定するための仕組み)。修正前の`provisioning\_agent.provision\_sanctuary()`は、(1)この場で新規にRSA鍵対を生成し、(2)その秘密鍵で証明書ペイロードに自ら署名し、(3)`maquina\_gatekeeper.py`の`MAQUINA\_PUBLIC\_KEY\_PEM`を正規表現置換でその場で生成した公開鍵に直接書き換え、(4)署名済み証明書をそのまま`ataraxia\_certificate.json`として発行していた。審査者(信頼の起点)と被審査者(証明書の発行者)が同一であるため、本スクリプトを実行できる者なら誰でも無条件に自分自身を「承認済み」にでき、ライセンス証明書機構は実質的に何の認可も提供していなかった。

\*\*修正\*\*: 鍵対生成と署名はその場で行うが、`maquina\_gatekeeper.py`の書き換えと証明書の発行は行わず、`sefer/provisioning\_pending.json`への提案キューイングに留めるよう変更した。新設した`tools/promote\_provisioning\_seal.py`で、人間が提案内容(client\_id・hardware\_fingerprint・有効期限)を確認した上で明示的に`--approve`して初めて、信頼の起点の更新と証明書発行が行われる。`tools/promote\_shield\_seal.py`・`tools/promote\_ledger\_seal.py`と同一のパターン。`tests/test\_provisioning\_approval\_flow.py`で回帰を固定した(実行環境に`rsa`パッケージ(PyPI)がインストールできないため、署名の暗号学的正しさ自体はテスト範囲外とし、「どのファイルが・いつ・何を書き換えるか」という構造を検証する疑似実装で代替している)。

\*\*その他確認済み(変更不要)\*\*: `adapters/excel\_to\_yaml\_parser.py`・`adapters/external\_qa\_wrapper.py`は、`angels/\_common.py`のdocstringが言及する刷新前の`print('initialized...')`プレースホルダーのまま残存していることを確認したが、CIワークフロー上は情報収集的な位置づけのステップであり、`angels/`の検査ステップ群のような合否判定の実体を持つ必要はないため、今回は現状維持とした。`sefer/\_\_init\_\_.py`(Sanctum)・`anjo\_interceptor/intent\_checker.py`・`tartarus/armageddon.py`・`tartarus/armageddon\_core.py`・`tools/`配下の各ツールは実質的な重複・演出のみのコードは見つからなかった。



\### P. リポジトリルート直下の未棚卸しファイルの整理

2026-10、`src/`・`angels/`・`sefer/`・`anjo\_interceptor/`・`adapters/`・`tartarus/`・`tools/`に続き、これまで未調査だったリポジトリルート直下のファイル群を棚卸しした。

\*\*削除(旧プロジェクト名`merkabah`への参照が残る死んだコード)\*\*:
\- `test\_archangels.py` / `test\_doctrines.py` / `test\_parasite.py` / `demo\_honeypot.py` — いずれも`tests/`配下ではなくリポジトリルート直下に置かれ、存在しない`merkabah`モジュールを`import`していた(`find . -iname "merkabah\*"`で確認した通り、現リポジトリ内に`merkabah`という名のモジュールは一切存在しない)。実行すれば`ModuleNotFoundError`で即座に失敗する。`git log --follow`で確認した通り、これらは本リポジトリの最初のコミット(`4f1b48a`、Merkabahからの改名後にリポジトリ全体を一括投入したコミット)の時点から既に死んでいた、改名時に取り残された残骸であり、他のどのファイルからも参照されていない(grep済み)。

\*\*削除(旧プロジェクト名の空の残骸ファイル)\*\*:
\- `chotam-merkabah` — 0バイト、拡張子なし。旧プロジェクト名`merkabah`を含むファイル名で、内容は空、他のどこからも参照されていない。
\- `README\_UNDERGROUND.md` — 0バイト。内容が一切なく、他のどこからも参照されていない。

\*\*削除(機能として一切配線されていない未使用スタブ)\*\*:
\- `registry.json` — `{"verified\_clients": {}, "revoked\_clients": []}`という構造を持つが、`registry.json`・`verified\_clients`・`revoked\_clients`のいずれの文字列も、`.py`/`.md`/`.yml`/`.html`のどのファイルからも一切参照されていない(grep済み)。`maquina\_gatekeeper.py`のクライアント証明書機構とは別に、クライアントの検証済み/失効済み状態を追跡する機能が将来的に意図されていたと推測されるが、配線された形跡が一切なく、現時点では実体を持たない死んだスタブと判断した。

これら7ファイルはいずれも上記コミット`4f1b48a`以降一度も変更されておらず、`--follow`付きの個別`git log`で確認した通り独自の変更履歴を持たない。

\*\*修正: `COMMANDS.md`の証明書再発行手順が§Oの修正前の挙動を記述したまま残存していた\*\* — §Oで`adapters/provisioning\_agent.py`を「提案キューイング＋人間承認」方式に修正したにもかかわらず、`COMMANDS.md`の「🔑 証明書（ataraxia\_certificate.json）の再発行」節は、修正前の「`provisioning\_agent.py`実行後、`ataraxia\_certificate.json`と`maquina\_gatekeeper.py`の両方を即座にコミットする」という旧い自己署名の運用手順を記述したまま残っていた。`tools/promote\_ledger\_seal.py`・`tools/promote\_shield\_seal.py`と同じ形式で、`tools/promote\_provisioning\_seal.py`による`--list`/`--approve`/`--reject`の手順に書き直した。

\*\*確認済み(変更不要・削除候補ではあるが本修正の範囲外として報告のみ)\*\*:
\- `assets/demo.mp4`(約11MB) — `README.md`・`architecture.html`のいずれからも参照されていない。リポジトリを11MB肥大化させているが、ユーザー自身が保持しているデモ録画である可能性があり、メディアファイルの削除は後戻りしにくい判断のため、本修正では削除せずユーザーへの報告事項とした。
\- `MANIFEST.in`・`shield\_rules.json`・`hooks/pre-commit`・`dummy\_secrets/`・`COMMANDS.md`(証明書節以外)・`architecture.html` — いずれも実際に参照され機能している、または意図的なハニーポット/ドキュメントであることを確認した。`sefer.egg-info/`は`.gitignore`の`\*.egg-info/`パターンにより元々Git管理外であることを確認した(pip editable installのビルド成果物)。
\- `zk\_audit\_report.xml` — `adapters/junit\_xml\_exporter.py`・`angels/heavenly\_tablets\_zkp.py`が生成する成果物だが、`.gitignore`の対象になっておらずコミット済みの内容は古い実行結果のスナップショットになっている。`sefer/audit\_chain.jsonl`と同種の「テスト実行で汚染されるがgit管理されている」ファイルであり、本修正の範囲外として変更しなかった(将来的に`.gitignore`への追加を検討する価値はある)。



\### Q. `assets/demo.mp4`の削除、`zk\_audit\_report.xml`のGit管理除外、`architecture.html`の旧プロジェクト名修正

§Pで「ユーザー判断待ち」として報告した2点につき、ユーザー承認を得て対応した。

\*\*削除: `assets/demo.mp4`(約11MB)\*\* — `README.md`・`architecture.html`のいずれからも参照されておらずリポジトリを不必要に肥大化させていたため削除した。

\*\*`.gitignore`に`zk\_audit\_report.xml`を追加しGit管理から除外\*\* — `adapters/junit\_xml\_exporter.py`・`angels/heavenly\_tablets\_zkp.py`がCI実行時に都度生成する成果物であり、`zk\_audit\_trail.json`(既に`.gitignore`対象)と対になるファイルであるにもかかわらず、こちらは対象外になっていた。コミット済みだった古い実行結果のスナップショットは`git rm --cached`でGit管理のみ外した(ローカルファイルは残置)。

\*\*修正: `architecture.html`に残っていた旧プロジェクト名`Merkabah`\*\* — `<title>`・見出し(`<h1>`)・本文中の3箇所に、改名(Merkabah→Pleroma)前の旧名称がそのまま残っていた。いずれも単純な名称置換で`Pleroma`に修正した。

\*\*確認済み(報告のみ・本修正では変更せず)\*\*: `architecture.html`はRaphael/Gabriel/Michaelの3要素と`rubric.json`・`homilies/`プラグイン機構を中心に説明する、現行実装(30件超の`angels/`検査・Sanctum・AegisSystem等)よりかなり早期の構想段階の設計を記述したドキュメントだった。`rubric.json`・`homilies/`はいずれも`.gitignore`にエントリがあるが、どちらも現在のリポジトリ内には実体が存在せず、どの`.py`ファイルからも参照されていない(未実装の将来機能、または構想段階で後に別アーキテクチャに置き換わった名残と推測される)。名称の修正のみ行い、内容全体を現行アーキテクチャに合わせて書き直すかどうかはユーザー判断に委ねる。



\### R. `Dockerfile`のCOPY漏れを修正(ビルドしても大半のテストが失敗していた不備)

\*\*事実確認\*\*: `git log --oneline -- Dockerfile`より、本ファイルはリポジトリ最初のコミット(`4f1b48a`)以来一度も変更されておらず、今回の一連の棚卸し・修正が原因で後から壊れたものではなく、\*\*最初から一度も正しく動く状態になったことがない\*\*ファイルだったことを確認した(ユーザーへの事実確認に対する回答として記録)。

\*\*不備の内容\*\*: 修正前は`COPY requirements.txt .`・`COPY maquina\_gatekeeper.py .`・`COPY tests/ tests/`の3点のみをイメージにコピーしており、テストが実際に`import`する`sefer/`・`angels/`・`adapters/`・`anjo\_interceptor/`・`src/`・`tartarus/`・`tools/`が一切含まれていなかった。Dockerが使えない本環境の制約上、実際の`docker build`では検証できなかったため、`.dockerignore`相当の除外ルールを適用した一時ディレクトリへ`cp`で再現し、そこで`mini\_pytest.py`シムを実行して実機相当の検証を行った。修正前の構成を再現した場合は`PASS=1 FAIL=25 ERROR=12`で大半が`ModuleNotFoundError`により失敗することを確認し、不備の実在を裏付けた。

\*\*修正\*\*: 個別ファイルの列挙は新しいディレクトリの追記漏れを構造的に誘発する(今回の不備そのものがその実例)ため、`COPY . .`でリポジトリ全体をコピーし、イメージに含めたくないもの(`.git`・`.github`・ビルド/キャッシュ生成物・ホスト/マシン固有の`ataraxia\_certificate.json`・テスト実行で汚染される各種監査ログ等)は新設した`.dockerignore`側で除外する方式に変更した。`ataraxia\_certificate.json`をイメージに焼き込まない方針は、`docker-compose.yml`が同ファイルを実行時に読み取り専用でマウントする既存の設計(ハードウェア指紋がマシン固有であるため)と整合する。

修正後の構成を同様に`cp`で再現し`mini\_pytest.py`を実行した結果、本修正前の(Dockerを経由しない)ローカル実行と同一の`PASS=78 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)となり、修正を確認した。

\*\*今回は変更しなかった点(ユーザーへの報告のみ)\*\*: `docker-compose.yml`の`network\_mode: "none"`はそのまま維持した。テストスイート(`tests/\*.py`)はいずれも実ネットワーク通信を直接行わない(grep済み)ため、デフォルトの`CMD ["pytest", "tests/", "-v", "-s"]`の実行自体はネットワーク遮断下でも成立する。一方、`docker-compose.yml`がマウントする`oracle\_output/`ディレクトリは、どの`.py`ファイルからも書き込み先として参照されておらず(grep済み)、実運用エージェント(`src/ollama\_agent\_loop.py`等、ローカルOllamaサーバーへのネットワーク到達が必要)を本コンテナで動かす用途は現状の設定とは整合しない。本コンテナの実際の用途を「テスト専用」と定めるか「実運用エージェント用」と定めるかは設計判断であり、今回はテストが通ることの確認のみに修正範囲を留めた。



\### S. `docker-compose.yml`の用途を「テスト専用サンドボックス」として確定、死んだ`oracle\_output`マウントを削除

§Rで保留にしていた設計判断(`docker-compose.yml`の`network\_mode: "none"`と実運用エージェントの用途整合性)について、ユーザー承認を得て方針を確定した。

\*\*判断根拠\*\*: `README.md`・`COMMANDS.md`のどちらにも`docker-compose`自体への言及が一切無く、本コンテナを「ローカルOllamaサーバーと通信する実運用エージェントの実行環境」として使う計画の裏付けが見当たらなかった。一方`Dockerfile`のデフォルト`CMD`は`pytest tests/`であり、これが唯一確認できる実利用経路である。架空の将来用途を推測して再設計するより、裏付けのある現状の用途(テスト実行)に合わせて明確化する方が安全と判断した。

\*\*修正\*\*: `network\_mode: "none"`はそのまま維持し、「テストスイートがネットワーク通信を一切発生させないことを前提にした、テスト専用・ネットワーク遮断サンドボックス」という用途をコメントで明記した。実運用エージェントをOllamaと通信させて動かしたい場合は、本コンテナの外(ホスト上で直接実行)か、`network\_mode`を緩めた別のcomposeサービスを別途新設する必要がある旨も明記した。あわせて、どの`.py`ファイルからも参照されていなかった死んだ`oracle\_output/`ボリュームマウントを削除した。`ataraxia\_certificate.json`(読み取り専用マウント)・`zk\_audit\_trail.json`(`maquina\_gatekeeper.py`の`ZKAuditTrail`が書き込む)は実際に使われていることを確認し、変更していない。



\### T. `architecture.html`の内容を現行実装に合わせて全面的に書き直し

§Qで名称修正のみに留め、ユーザー判断待ちとして報告していた「内容全体を現行アーキテクチャに合わせて書き直すか」について、ユーザー承認を得て実施した。

\*\*事実確認\*\*: 修正前の`architecture.html`は、Raphael/Gabriel/Michaelの3カード構成の「Canon」節に続けて、`rubric.json`・`homilies/`という外部プラグイン機構を中心に説明する「Local Doctrines」節を持っていた。しかし`rubric.json`・`homilies/`はリポジトリ内に実体が存在せず(§Qで確認済み)、どの`.py`ファイルからも参照されていない構想段階の記述だった。Gabriel(`sefer.inquisition()`によるASTスキャン)とMichael(`sys.addaudithook`ベースの`\_michael\_absolute\_defense`)の説明内容自体は現行の`sefer/\_\_init\_\_.py`の実装と一致していたが、Raphaelの説明(「環境監視」)は実際には`sefer`パッケージの外にある別モジュール`maquina\_gatekeeper.py`(RSA署名+ハードウェア指紋による証明書ゲート、§Oで人間承認フローに修正済み)の役割に近く、不正確だった。また`src/aegis\_system.py`(`AegisSystem`、4層構成の実行ガード)と`angels/`配下の約34件のCI検査スクリプト、`tartarus/armageddon.py`のLucifer/Metatron自己対戦サイクルは、いずれも現行実装の中核でありながら本ドキュメントに一切記載が無かった。

\*\*修正\*\*: `<body>`内容を3節構成に書き直した。(1)「The Canon (Core Absolute Defense — sefer.Sanctum)」: Gabriel・Michaelは実装と一致していたため`sefer.inquisition()`・`\_michael\_absolute\_defense`への言及を補強する形で維持し、Raphaelは`maquina\_gatekeeper.py`の役割(ライセンス・環境シール)として再定義、§Oの人間承認フローへの言及も追加した。(2)「AegisSystem (4-Layer Execution Guard)」: IntentInterceptor(`anjo\_interceptor/`、ハニーポット・パストラバーサル検知)・WorkspaceJail(`secure\_resolve()`によるパス封じ込め)・Sandalphon(`--network none`のDockerジェイル)の3カードを新設し、存在しなかった「Local Doctrines」節を置き換えた。(3)「The Angels (Blue-Team CI Audit Layer)」: `angels/`配下の約34件の検査スクリプトと、Lucifer/Metatronによる自己対戦進化サイクル(提案は`tools/promote\_ledger\_seal.py`による人間承認を経るまで適用されない、既存の人間承認ゲートパターンと一致)を新設した。既存のCSSクラス(`card raphael`/`gabriel`/`michael`/`extension`、`.icon`・`.tech-stack`)のみを再利用し、新規CSSの追加は行っていない。

\*\*検証\*\*: `html.parser`による開始/終了タグの対応チェックで構文的に整形が崩れていないことを確認した。`MANIFEST.in`の`exclude architecture.html`は内容変更の影響を受けないため変更不要であることを確認した。`mini\_pytest.py`実行結果は本修正前と同一の`PASS=78 XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)であり、本ファイルを直接参照するテストが無いことと整合する想定通りの結果だった。



\### U. `COMMANDS.md`に実運用エージェントループ(`ollama\_agent\_loop.py`/`openai\_agent\_loop.py`)の起動手順を追記、既存ERROR2件の原因を調査

ユーザーから「さらに増築できるところはないか」との依頼を受けて棚卸しを行い、実装済みだが未ドキュメント化だった機能の補完と、`mini\_pytest.py`実行結果に残っていた既存ERROR2件の原因調査を行った。

\*\*追記: `src/ollama\_agent\_loop.py`・`src/openai\_agent\_loop.py`の起動手順\*\*。両ファイルとも実装自体は既に完成しており(Sanctum/AegisSystem/maquina\_gatekeeperの全防御層を統合済み)、`README.md`にアーキテクチャの説明はあったが、`COMMANDS.md`にはこれらを実際に動かすコマンドの記載が一切無かった。`ollama\_agent\_loop.py`は`python src/ollama\_agent\_loop.py`で直接実行可能、`openai\_agent\_loop.py`は`\_\_main\_\_`を持たないテンプレートクラスのため呼び出し側コードの例を示した。両方ともDockerデーモンの起動が前提(Sandalphon層がコンテナ内で動的実行検証を行うため、デーモン不在時はフェイルクローズで全実行を拒否する)である旨も明記した。

\*\*調査: `mini\_pytest.py`実行結果の既存ERROR2件の原因\*\*(いずれも本リポジトリのバグではなく、検証環境側の制約であることを確認。修正は行っていない):
\- `tests/test\_openai\_agent\_loop\_template.py`: `ModuleNotFoundError: No module named 'rsa'`。`rsa==4.9`は`requirements.txt`に正しく記載されているが、本検証環境はネットワークが遮断されており(`pip install`が名前解決エラーで失敗)インストールできない。リポジトリ側の不備ではなく環境側の制約。
\- `tests/test\_sanctuary.py`: `TypeError: _Mark.xfail() got an unexpected keyword argument 'condition'`。テスト本体の`@pytest.mark.xfail(condition=..., raises=..., strict=...)`は実際のpytestが正式サポートする標準的な書き方であり誤りではない。本検証環境に実pytestをインストールできないため代用している自作シム`mini\_pytest.py`(本リポジトリの一部ではない)が`condition`引数を実装していないために発生するエラーで、リポジトリ側の不備ではない。

\*\*調査: `sefer.Sanctum`の`restrict\_reads`デフォルト値をTrueに変更すべきか\*\*(ユーザーへの提案として自分で出していた検討事項)。実際に本番相当のエージェントループである`src/ollama\_agent\_loop.py`・`src/openai\_agent\_loop.py`はいずれも既に呼び出し時に明示的に`restrict\_reads=True`を指定しており、ライブラリ側のデフォルト値(`False`、後方互換のため)が実際の防御レベルに影響する呼び出し箇所は現状存在しないことを確認した(`angels/\_common.py`の検査用サブプロセステンプレートも`restrict\_reads`を指定しない汎用ハーネスであり、読み取り制限の検証自体を目的としていないため対象外)。また`tests/test\_read\_restriction.py`はデフォルト`False`での後方互換動作を正式な期待結果として検証している。実運用側には防御漏れが無く、デフォルト値の変更は後方互換テストの意図的な破壊になるため、\*\*変更は行わなかった\*\*。



\### V. `COMMANDS.md`に`metatron\_orchestrator.py`(完全自動化防衛ループ「聖戦」)の起動手順を追記

§Uと同じ趣旨の棚卸しの続きとして、もう一つ未ドキュメント化だった実装済み機能を発見し補完した。

\*\*追記内容\*\*: `src/metatron\_orchestrator.py`の`MetatronOrchestrator.execute\_holy\_war()`は、ラジエル(`intelligence\_cycle.RazielIntelligence`、偵察)→サマエル(`intelligence\_cycle.SamaelWeaponization`、ローカルOllamaによる攻撃コード生成)→天使(`angelic\_evolution.EvolvingAngel`、Blue Team=Gabriel静的解析+Sandalphon動的隔離検証)→ガブリエル(`GabrielRevelation`、Markdownレポート生成)を1サイクルとして自動実行する、実装済みの完全自動化防衛ループである。`if \_\_name\_\_ == "\_\_main\_\_"`から直接実行可能(`python src/metatron\_orchestrator.py`)だが、`COMMANDS.md`・`README.md`のいずれにもこの起動方法の記載が無かった。実行には(§Uのollama\_agent\_loop同様)Ollamaと稼働中のDockerデーモンの両方が必要であること、結果が`revelations/gabriel\_revelation\_<サイクルID>.md`に出力されることを明記した。

\*\*確認\*\*: `deadmans\_switch.CollarProtocol`が要求する環境変数`ANJO\_COLLAR\_SEAL`は、呼び出し元の`intelligence\_cycle.py`モジュール読み込み時に自動設定される(`os.environ["ANJO\_COLLAR\_SEAL"] = "VALID\_MYTHOS\_SEAL\_999"`)ため、利用者が追加で設定する必要はないことを確認した。

ドキュメントのみの追記のため、`mini\_pytest.py`実行結果は変更前と同一の`PASS=78 XFAIL=2 FAIL=0 ERROR=2`であることを確認した。



\### W. `IntentInterceptor`が正当な`"list"`アクションを「未許可のアクション」として誤検知・遮断していた不具合を修正

ユーザーの実機検証(`python src/ollama\_agent\_loop.py`の実行)に付随して行った、検知ルールの棚卸しの中で発見した実バグ。過剰検知(false positive)であり、セキュリティホールではないが、機能そのものが使用不能になっていた。

\*\*事実確認\*\*: `src/ollama\_agent\_loop.py`の`_execute\_safe\_action`は`"list"`アクションを正式に実装しており(§Mで`final\_agent\_loop.py`から統合)、システムプロンプト中の出力フォーマットにも`"action": "read" | "write" | "list"`と明記されている。しかし`anjo\_interceptor/intent\_checker.py`の`IntentInterceptor.allowed\_actions`は`{"read", "write"}`のままで、`"list"`が含まれていなかった。`run\_task()`のループでは実行前に必ず`IntentInterceptor.evaluate\_action()`を通すため、AIが`"list"`を申請すると、実装が存在するにもかかわらず常に「[暴走検知] 未許可のアクション 'list' を検知しました」として遮断され、事実上使用不能だった。実機で`interceptor.evaluate\_action(json.dumps({"action": "list", "target": "."}))`を実行し、`SpecificationGamingDetected`が発生することを確認して再現した。

\*\*修正\*\*: `allowed\_actions`に`"list"`を追加した。`"list"`の実際の安全性(ディレクトリトラバーサル対策等)は、既存の`WorkspaceJail.secure\_resolve()`(§Mで確認済み、`tests/test\_ollama\_agent\_loop\_list\_action.py`で担保済み)が別途担っており、`IntentInterceptor`側で追加の検証を行う必要はないため、他のロジックは変更していない。

\*\*テスト\*\*: `tests/test\_intent\_gaming.py`に`test\_list\_action\_is\_not\_blocked\_as\_unauthorized`を追加し、`"list"`が正常に通過することを固定した。`mini\_pytest.py`実行結果は`PASS=79`(新規追加分+1)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)で、既存の防御(ハニーポット・トラバーサル・深層AST検閲・不正アクション検知)が壊れていないことを確認した。



\### X. `sefer/audit\_chain.jsonl`(Michaelの実監査ログ)が`.gitignore`対象外でGit管理されていた不備を修正

可視化ダッシュボードの作成に着手する前段として、データ元となるファイル群を点検した際に発見した。§Qで`zk\_audit\_report.xml`について見つけたのと同種の見落としが、別のファイルにも残っていた。

\*\*事実確認\*\*: `sefer/audit\_chain.jsonl`は、`sefer.\_log\_violation\_to\_chain()`(Michaelが実際にイベントを遮断した際に呼ばれる)が都度追記する、ハッシュ連鎖による改ざん検知付きの実監査ログである。`zk\_audit\_trail.json`(`maquina\_gatekeeper.ZKAuditTrail`が書き込む、同種の実行時生成ログ)は`.gitignore`で正しく除外されていたが、`sefer/audit\_chain.jsonl`は除外対象になっておらずGit管理下に置かれていた。Sanctumの遮断挙動を検証する大半のテスト(`test\_sanctuary.py`・`test\_sandbox.py`等)が実際に遮断イベントを発生させるため、`mini\_pytest.py`を実行するたびに本ファイルが汚染され、これまで毎回`git checkout --`で手動で元に戻す必要があった。

\*\*修正\*\*: `.gitignore`に`sefer/audit\_chain.jsonl`を追加し、`git rm --cached`でGit管理のみ外した(ローカルファイルは残置)。あわせて、同じ「人間承認待ちキュー」のパターンに属する`shield\_rules\_pending.json`・`provisioning\_pending.json`(既に`raziel\_ledger\_pending.json`は対象だったが、この2つが対象外のまま漏れていた)も`.gitignore`に追加し、将来`git add -A`等で誤ってコミットされる事故を未然に防いだ(現時点ではまだGit管理下に入っていないため実害は無かったが、再発防止の予防的修正)。

ドキュメントのみ・Git管理設定のみの変更のため、`mini\_pytest.py`実行結果は変更前と同一の`PASS=79 XFAIL=2 FAIL=0 ERROR=2`であることを確認した。



\### Y. 防衛ダッシュボード(`tools/generate\_dashboard.py`)を新設

ユーザーからの「記録室を作る(可視化・ダッシュボード)」という依頼に基づき新設した。これまでArmageddon Engineの戦績・Michaelの実遮断ログ・現在の禁止イベント一覧・各種人間承認待ちキューは、個別に`cat`するしかなく、全体の傾向を一目で把握する手段が無かった。

\*\*実装\*\*: `tools/generate\_dashboard.py`が以下を読み取り、単一の自己完結したHTML(`dashboard.html`、外部CDN等への依存なし・オフライン閲覧可能)にまとめる。
\- `tartarus/akashic\_records.json` — Armageddon Engine(Lucifer vs Metatron)の戦績。総戦績数・突破された回数・防御成功率・QAスコアの推移(簡易SVGグラフ)・直近20件の戦闘記録表
\- `sefer/audit\_chain.jsonl` — Michaelが実際に遮断したイベントの監査ログ。総遮断件数・イベント種別ごとの件数(簡易SVGグラフ)
\- `sefer/raziel\_ledger.json` — 現在有効な禁止イベント一覧
\- `sefer/raziel\_ledger\_pending.json`・`shield\_rules\_pending.json`・`provisioning\_pending.json` — キュー別の人間承認待ち件数

いずれのデータファイルも「存在しない場合」(初回実行時や、該当する防衛サイクルを一度も回していない場合)を例外を出さずに「データがありません」等で表示できるよう設計した。`build\_dashboard()`は各データファイルのパスを明示的に注入できるようにし、実データに依存せずテストできる構造にした。

\*\*テスト\*\*: `tests/test\_generate\_dashboard.py`を新設し、架空データでの集計結果の反映確認、および全データファイルが存在しない場合でも例外なく生成できることを固定した。`mini\_pytest.py`実行結果は`PASS=81`(新規+2)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

\*\*その他\*\*: 生成物`dashboard.html`はビルド成果物のため`.gitignore`に追加し、Git管理対象外とした。`COMMANDS.md`に起動コマンド(`python tools/generate\_dashboard.py`)を追記した。



\### Z. `FutilityGuard`(新しい防御層)を新設 — 「進展が見込めない繰り返し」を検知して早期終了

ユーザーからの「新しい門を作る(新規防御機能の追加)」という依頼に基づく。当初は別のAIプロバイダ(Claude等)向けの新しい実行ループファイルの新設も検討したが、GRIMOIRE.md §Mで「新しい実運用ループを作る前に既存の`ollama\_agent\_loop.py`/`openai\_agent\_loop.py`の拡張を検討すること」という方針を既に記録済みであり、新規ファイルの増殖は過去に実際に問題を起こした構造的リスクそのものだったため、新規ループファイルは作らず、既存の両ループに新しい防御層を追加する方針に変更した。

\*\*着想\*\*: ユーザー自身による実機検証(`python src/ollama\_agent\_loop.py`の実行)で、ローカルLLM(llama3.1)が存在しない架空のパス(`/path/to/database/config/file`)への`"read"`を5ステップ連続で繰り返し、何も得られないまま`max\_steps`を使い切って終了する挙動が実際に観測された。各ステップ単体はGabriel・IntentInterceptor・Sandalphon・Sanctumのいずれにも異常なく処理を完了しており(危険な操作でもないため)、既存のどの防御層にも引っかからない「無駄な繰り返し」だった。これはSandalphonの実行タイムアウト(1回の実行が長すぎることへの防御)とは異なる観点の問題である。

\*\*実装\*\*: `src/futility\_guard.py`を新設し、`FutilityGuard`クラスを両ループ(`ollama\_agent\_loop.py`・`openai\_agent\_loop.py`)で共有する(同じ修正を2箇所に別々に実装すると、§Mで実際に発生したのと同種の「片方にしか修正が入らず他方が取り残される」リスクを再現するため、共有モジュールとした)。同じ`(action, target)`の組み合わせが既定で2回を超えて繰り返された場合(3回目)、「[システム: 空転検知]」としてループを早期終了する。判定対象は`action`/`target`のみで、`content`(AIが生成する補助的なコード片)は意図的に対象外とした(実機検証で、AIが同じaction/targetに対し毎回微妙に異なるcontentを生成し続ける挙動が確認されたため)。判定はAegis/Sandalphonの呼び出し\*\*前\*\*に行うため、空転が検知された場合はDockerの起動すら発生せず、無駄なリソース消費も削減される。

\*\*テスト\*\*: `tests/test\_futility\_guard.py`(単体: カウンタロジック)、`tests/test\_futility\_guard\_integration.py`(統合: 固定応答のOllamaスタブで`run\_task()`が実際に`max\_steps=5`を使い切る前に3ステップで早期終了することを検証。Dockerデーモン不要)を新設した。`mini\_pytest.py`実行結果は`PASS=87`(新規+6)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

\*\*ドキュメント\*\*: §Tで全面書き直したばかりの`architecture.html`に「Agent Loop Resilience」節を新設し、`FutilityGuard`がAegisSystemの一部ではなく、エージェントループ自身がAegisSystem呼び出し\*\*前\*\*に適用する別レイヤーであることを明記した(不正確な記述を防ぐため)。



\### AA. `WorkspaceJail.secure\_resolve()`の脱走判定に、文字列前方一致による重大なバイパス脆弱性を発見・修正

ユーザーからの「さらなる進化を」という依頼を受けて行った追加調査で発見した、これまでの棚卸しの中で最も深刻な実セキュリティホール。

\*\*事実確認\*\*: `src/workspace\_manager.py`の`WorkspaceJail.secure\_resolve()`は、解決済みパスが牢獄(`base\_dir`)の配下にあるかを`str(requested\_path).startswith(str(self.base\_dir))`という単純な文字列の前方一致のみで判定していた。これは末尾に区切り文字(`/`)を要求しないため、`base\_dir`と同じ文字列から始まる\*\*兄弟ディレクトリ\*\*(例: `base\_dir="jail\_workspace"`に対し`"jail\_workspace\_EVIL"`)へも、`".."`による1階層分の脱走だけで到達できてしまう、古典的かつ深刻な欠陥だった。実機で以下を検証し再現した:

```python
jail = WorkspaceJail(base_dir="/tmp/xxx/jail_workspace")
jail.secure_resolve("../jail_workspace_EVIL/secret.txt")
# => 修正前: 遮断されず /tmp/xxx/jail_workspace_EVIL/secret.txt を返してしまう
```

このクラスは`"list"`アクションの境界保護(§M参照)や`AegisSystem`(`src/aegis\_system.py`)自体が依拠する、ワークスペース隔離の核となる機構であるにもかかわらず、長期間この脆弱な判定方法のまま見過ごされていた。一方で`sefer/\_\_init\_\_.py`(Sanctum/Michael側)は、同種の判定に既に`Path.is\_relative\_to()`を正しく使っており、`WorkspaceJail`だけがこの古い脆弱な実装のまま取り残されていたことも確認した。

\*\*修正\*\*: `str(...).startswith(str(...))`を、`requested\_path != self.base\_dir and not requested\_path.is\_relative\_to(self.base\_dir)`というパスオブジェクトとしての厳密な判定に置き換えた。`!= self.base\_dir`の除外は、`target\_path="."`(牢獄そのものへのアクセス。`"list"`アクション等で正当に使われる)を誤って遮断しないための配慮。

\*\*テスト\*\*: `tests/test\_workspace\_jail.py`を新設し、(1)正常なアクセスの許可、(2)古典的な`"../../../etc/passwd"`型トラバーサルの遮断、(3)今回発見した「前方一致バイパス」(兄弟ディレクトリへの脱走)の遮断、(4)牢獄自身への正当なアクセスの許可、の4パターンを固定した。`mini\_pytest.py`実行結果は`PASS=91`(新規+4)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)で、既存の`"list"`アクション・`AegisSystem`の挙動が壊れていないことも確認した。



\### AB. 同種の文字列前方一致バイパスが`angels/\_common.py`のシークレット漏洩スキャナにも存在していたため修正

§AAで`WorkspaceJail`に見つけた脆弱性パターン(文字列の前方一致のみによる境界判定)が、リポジトリ内の他の場所にも残っていないか`grep`で横断的に点検した結果、もう一箇所で発見した。

\*\*事実確認\*\*: `angels/\_common.py`の`scan\_for\_leaked\_secrets()`(CI上でシークレット漏洩を検知する`angels/gabriel\_canary.py`が使用)は、スキャン除外対象のディレクトリ(`EXCLUDED\_SECRET\_SCAN\_DIRS = {"dummy\_secrets", ".git", "\_\_pycache\_\_", "sefer/.angel\_state", "revelations"}`)との一致判定を`rel.startswith(ex)`という文字列の前方一致のみで行っていた。これは末尾の区切り文字を要求しないため、`"dummy\_secrets\_backup/real\_leaked\_key.env"`のように、除外対象の名前と前方一致するだけの別ディレクトリに置かれた本物のシークレットも、スキャン自体が一切行われずに素通りしてしまう欠陥だった(実機で再現を確認)。これは`WorkspaceJail`の脆弱性とは逆方向(過剰な除外によるセキュリティ機能自体の無効化)だが、根本原因は同一(末尾区切り文字を要求しない文字列前方一致)である。

\*\*修正\*\*: `rel == ex or rel.startswith(ex + "/")`という、完全一致またはそのディレクトリ配下(区切り文字付き)であることを要求する判定に修正した。テスト容易性のため`scan\_for\_leaked\_secrets()`に`root`引数を追加し(既定はリポジトリ本体の`ROOT`)、一時ディレクトリ上の架空のファイル構成で検証できるようにした。

\*\*テスト\*\*: `tests/test\_scan\_for\_leaked\_secrets.py`を新設し、(1)正規のハニーポット(`dummy\_secrets/`)は引き続き除外される、(2)今回発見した「前方一致バイパス」(`dummy\_secrets\_backup/`)に置かれたシークレットは正しく検知される、(3)通常のディレクトリのシークレットも検知される、の3パターンを固定した。`mini\_pytest.py`実行結果は`PASS=94`(新規+3)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。



\## 4. 創造主の絶対権限（The Creator's Air）

Tartarusのエンジンは、起動直後に `uuid.getnode()` を用いてホストマシンの物理MACアドレスを取得し、不可逆ハッシュ（SHA-256）に変換して検証する。

これにより、この神界の箱庭（Pleroma）がGit経由などで他者の手に渡っても、闘技場は決して開かれず、ルシフェルは即座に自壊する。この闘争は、創造主の監視下でのみ許される神聖な儀式として保たれる。


\### AC. `sefer/\_\_init\_\_.py`の`\_is\_path\_allowed()`に、大文字小文字を無視した文字列比較による境界バイパス脆弱性を発見・修正

ユーザーからの3度目の「更なる進化を」という依頼を受け、§AA・§AB で見つけた「境界判定の緩さ」というバグの系譜を追って、今度はMichaelの絶対防壁（`sys.addaudithook`によるOSレベルの実行時監視、`sefer/\_\_init\_\_.py`の`\_michael\_absolute\_defense()`）そのものの内部を精査した結果、同じ系譜に属する新たな脆弱性を発見した。

\*\*事実確認\*\*: `\_is\_path\_allowed(target\_path, allowed\_dirs)`は、まず`Path.is\_relative\_to()`による正しい判定を試みるが、それが`False`の場合に\*\*フォールバックの文字列比較\*\*へ進む。このフォールバックが`str(target).lower()`・`str(resolved\_d).lower()`という\*\*大文字小文字を無視した\*\*比較になっていた。これは、`allowed\_dirs`に指定したディレクトリと大文字小文字が異なるだけの、\*\*実在する完全に別のディレクトリ\*\*への書き込み・削除等の破壊的操作を許可してしまう欠陥である。Linuxのような大文字小文字を区別するファイルシステム上で、実機にて以下を再現・確認した:

```python
# allowed_dirs=["jail_workspace_repro"] のみを許可
with Sanctum(allowed_dirs=["/home/claude/pleroma/jail_workspace_repro"]):
    open("/home/claude/pleroma/JAIL_WORKSPACE_REPRO/evil.txt", "w")
    # => 修正前: 遮断されずに書き込みが成立してしまう
```

`jail\_workspace\_repro`と`JAIL\_WORKSPACE\_REPRO`は、ファイルシステム上では完全に無関係な別個の実ディレクトリであり、`allowed\_dirs`はどちらか一方しか許可していないにもかかわらず、大文字小文字を畳み込む比較のせいで「許可されたディレクトリの一部」であるかのように誤判定されていた。§AA(`WorkspaceJail`の前方一致バイパス)・§AB(シークレットスキャナの前方一致バイパス)はいずれも「区切り文字を要求しない前方一致」という同じ欠陥の系譜だったが、本件はその系譜とは別の軸（大文字小文字の畳み込み）による、同じ「境界判定の緩さ」という結果をもたらす脆弱性だった。このフォールバック自体はパス区切り文字(`\`→`/`)の正規化のみを目的としており、大文字小文字の無視は意図した挙動ではなかったと判断した。

\*\*修正\*\*: フォールバック文字列比較から`.lower()`を除去し、大文字小文字は元の文字列のまま厳密に比較するよう修正した。パス区切り文字の正規化のみは維持した。

\*\*テスト\*\*: `tests/test\_michael\_is\_path\_allowed.py`を新設し、(1)許可ディレクトリ配下への正当なアクセスの許可、(2)許可ディレクトリそのものへのアクセスの許可、(3)許可ディレクトリ外への通常のアクセスの遮断、(4)今回発見した「大文字小文字違いバイパス」(許可ディレクトリと大文字小文字が異なるだけの別の実ディレクトリ)の遮断、の4パターンを固定した。`mini\_pytest.py`実行結果は`PASS=98`(新規+4)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)で、`WorkspaceJail`・`AegisSystem`等の既存挙動が壊れていないことも確認した。

\### AD. `maquina\_gatekeeper.py`の「深層保護」(`ultimate\_audit\_hook`)が、子スレッド経由で完全にバイパス可能だった脆弱性を発見・修正

ユーザーからの3度目の「更なる進化を」という依頼を受けた棚卸しの続きで、`sefer/\_\_init\_\_.py`(Michael/Sanctum)の次に、ライセンス証明書ゲートである`maquina\_gatekeeper.py`を精査した結果、§AA〜§ACとは異なる種類の、より深刻な「保護層の完全な無効化」脆弱性を発見した。

\*\*事実確認\*\*: `enforce\_maquina\_seal`デコレータは、証明書検証に成功すると`set\_sanctuary\_sealed(True)`で「封鎖」状態に入り、デコレータ本体の処理が終わるまでの間、`sys.addaudithook`で登録された`ultimate\_audit\_hook`が`subprocess.Popen`・`os.system`・`os.exec`等の危険操作を遮断する「深層保護」が働く設計になっていた。しかし封鎖ステータスの実体である`\_thread\_state`は`threading.local()`(スレッドごとに独立)で実装されていた。`ultimate\_audit\_hook`自身は`sys.addaudithook`によりプロセス全体(全スレッド)で呼び出されるにもかかわらず、その中の`is\_sanctuary\_sealed()`判定がスレッドローカルであるため、封鎖済みのスレッドの中で新たなスレッドを一つ生成するだけで、その子スレッドでは`is\_sanctuary\_sealed()`が常に`False`(`threading.local()`の既定値)を返し、`ultimate\_audit\_hook`が検査そのものを一切行わずに即座にreturnしてしまう。実機で以下を再現・確認した:

```python
mg.set_sanctuary_sealed(True)
# メインスレッドでの禁止操作 → 正しく LossOfAtaraxia で遮断される
# しかし、その"封鎖中"に生成した子スレッドの中で同じ操作を行うと:
def evil_in_child_thread():
    subprocess.Popen(["echo", "ESCAPED_VIA_THREAD"], ...)  # => 遮断されず実行されてしまう
```

`enforce\_maquina\_seal`デコレータは`\_GLOBAL\_SANCTUARY\_LOCK`により呼び出し自体をプロセス全体で直列化しているため、複数スレッドが同時に独立した封鎖状態を持つ正当な理由はそもそも存在しない。むしろ`sefer/\_\_init\_\_.py`側の`\_active\_stack`(Michaelの絶対防壁の状態管理)は元々プロセス全体で共有するグローバルなリストとして実装されており、本件はそれとは逆に、本来共有すべき状態を誤ってスレッドローカル化してしまっていたことが原因だった。

\*\*修正\*\*: 封鎖ステータスを`threading.local()`から、ロックで保護したプロセス全体共有のグローバル変数(`\_is\_sanctuary\_sealed\_global`)に変更した。これにより、どのスレッドで封鎖しても、その封鎖状態は全スレッドから一貫して観測され、`ultimate\_audit\_hook`の検査を子スレッド経由で回避することはできなくなった。

\*\*テスト\*\*: `tests/test\_thread\_safety\_maquina\_seal.py`を新設し、(1)封鎖状態が子スレッドにも共有されること、(2)封鎖中は子スレッドからの禁止操作(`subprocess.Popen`)も遮断されること、(3)封鎖していない通常時は本フックによる誤検知が起きないこと、の3パターンを固定した。本物の`rsa`パッケージがこのサンドボックス環境のegressポリシー上インストールできないため、`tests/test\_provisioning\_approval\_flow.py`と同一の疑似実装パターンで`maquina\_gatekeeper.py`の`import rsa`を満たしている(ファイル名は`test\_openai\_agent\_loop\_template.py`より辞書順で後になるよう選定し、既存の「本物のrsaが無いことによるERROR」という既知の環境起因の挙動(§U参照)に影響を与えないようにした)。`mini\_pytest.py`実行結果は`PASS=101`(新規+3)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

\### AE. `sefer/audit\_chain.py`の`SignedAuditChain`が、名前の通り「署名付き」ではなく実際には無鍵のハッシュ連鎖に過ぎず、改ざん検知が無力化できる脆弱性を発見・修正

ユーザーからの3度目の「更なる進化を」という依頼を受けた棚卸しの続きで、§AD(`maquina\_gatekeeper.py`の深層保護バイパス)の次に、監査証跡そのものの信頼性を精査した結果、これまでとは異なる種類の脆弱性を発見した。これまでの§AA〜§ADは「防壁の抜け道」だったが、本件は「侵入された後の証拠そのものを消せてしまう」という、事後対応(フォレンジック)を無力化する脆弱性である。

\*\*事実確認\*\*: `sefer/audit\_chain.py`の`SignedAuditChain`クラスは、クラス名が「署名付き監査チェーン」と名乗り、`angels/zadkiel\_astrolabe.py`のコメントにも「署名付き監査チェーン」と明記されているにもかかわらず、実際にはSHA-256による単純なハッシュ連鎖(各エントリのハッシュを前エントリのハッシュに連結してハッシュ化するだけ)に過ぎず、秘密鍵や公開鍵署名など、いかなる暗号学的な「署名」も使っていなかった。これは「意図しない破損の検知」には有効だが、「ログファイルへの書き込み権限を持つ攻撃者による意図的な改ざん」には何の防御にもならない。実機で以下を再現・確認した:

```python
chain.record("AI_ACTION", {...})
chain.record("VIOLATION", {"message": "不正なアクセスを検知し遮断した"})  # 侵入検知の記録
chain.record("AI_ACTION", {...})

# 攻撃者が「VIOLATION」の行を削除し、残りのチェーンを先頭から
# 秘密鍵なしに再計算して書き直すだけで:
# => 修正前: verify_integrity() は改ざんを検知せず True を返し続けた
#    (つまり「侵入された証拠」を跡形もなく消せてしまう)
```

`sefer/\_\_init\_\_.py`の`\_log\_violation\_to\_chain()`も、本クラスとは独立に同じフォーマットのハッシュ連鎖ロジックを二重実装しており、片方だけ修正すると両者のフォーマットが食い違い`verify\_integrity()`自体が壊れるリスクも確認した。

この脆弱性が直接悪用できるのは「すでに`sefer.Sanctum`の外側(ホスト側、あるいは§AA〜§ADのような未知の脱走経路を突いた後)で任意のファイル書き込み権限を得た攻撃者」に限られる(`sefer/audit\_chain.jsonl`自体は通常`allowed\_dirs`の外にあり、Sanctum配下の未信頼コードからの直接書き込みはMichaelの絶対防壁により遮断されるため)。しかし、本フレームワーク全体が前提とする脅威モデルは「Sanctum配下に閉じ込めた未信頼AIコードの脱走防止」であり、万一将来何らかの未知の脱走経路が使われた場合に、侵入の証拠そのものを完全に消せてしまうというのは、監査証跡の存在意義そのものを損なう重大な設計上の欠陥と判断した。

\*\*修正\*\*: 各エントリのハッシュを、無鍵のSHA-256から、ローカルに自動生成・保管する秘密鍵(`sefer/.audit\_signing\_key`、初回生成時のみ0600権限で作成)を用いたHMAC-SHA256に変更した。鍵ファイルを読めない攻撃者は、チェーンの整合性を保ったまま既存エントリの改ざん・削除・偽装を行えなくなる。また`\_log\_violation\_to\_chain()`の独自実装を廃止し、`SignedAuditChain.record()`への委譲に一本化して二重実装の食い違いリスクを解消した。あわせて、文字列の`==`によるハッシュ比較を`hmac.compare\_digest()`による定数時間比較に変更した(タイミング攻撃への理論的な弱さの解消)。`key\_path`省略時の既定値を`log\_path`と同じディレクトリ基準にすることで、テストが実リポジトリの鍵ファイルを汚染しないようにもした。

\*\*残存する限界(誠実に明記する)\*\*: 本修正は「Sanctum配下でサンドボックス化された未信頼コードによる改ざん」への対策であり、鍵ファイル自体を読み書きできるホストOS上の特権(root等、サンドボックスの外側)を持つ攻撃者までは防げない。それは本フレームワークが前提とする脅威モデルの範囲外であり、外部の改ざん不可能な監査サービスやHSM等、別のアーキテクチャでしか解決できない限界であることを、誤解を避けるためここに明記する。

\*\*テスト\*\*: `tests/test\_audit\_chain.py`に2件追加し、(1)鍵ファイルを持たない別インスタンスでは正規のチェーンでも検証に失敗すること、(2)§AEの核心となる「VIOLATION行の削除+鍵なしでのチェーン再計算」という具体的な攻撃手口が、修正後は検知されること、を固定した(既存の2テストも維持)。`angels/zadkiel\_astrolabe.py`を実行し、実際のCI向け検査スクリプトが新方式でも正しく動作することも確認した。`mini\_pytest.py`実行結果は`PASS=103`(新規+2)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

なお、本修正によりハッシュ計算方式が変わるため、このサンドボックス環境でこれまでのテスト実行により生成されていた旧方式(無鍵SHA-256)の`sefer/audit\_chain.jsonl`(Git管理対象外のローカル専用ファイル)は、新方式では検証に失敗するようになる。実害のある本番監査ログではなく本セッションのテスト実行で生成された一時データのみだったため、削除してクリーンな状態からHMAC方式での記録を開始した。

\### AF. §Jで保留されていた`src/ast\_scanner.py`の統合判断を確定(非統合・保持)

ユーザーからの3度目の「更なる進化を」という依頼を受けた棚卸しの続きで、`src/aegis\_system.py`(AI生成コードの実運用審査パイプライン)が実際に何を検閲しているかを精査する過程で、`src/ast\_scanner.py`の`CognitiveScanner`が、どこからもimportされず`tests/test\_ast\_scanner\_qualified\_calls.py`で単体テストされるだけの孤立モジュールであることに気づいた。GRIMOIRE.md §Jで「検知漏れバグは修正したが、実運用パイプラインへの統合判断は保留」と記録されたまま、その後の§K・§L(他の未統合スタンドアロンデモの統合/削除判断)でも扱われずに残っていた未決事項だった。

\*\*検討\*\*: 本モジュールの`banned\_modules = {'os', 'sys', 'shutil', 'subprocess'}`は、既に`aegis\_system.py`経由で実運用されているGabriel(`sefer.inquisition()`)の`forbidden\_modules`(pickle/ctypes/importlib/socket/urllib/requests/http/subprocess/os)より広く、`sys`・`shutil`の単純importだけで即座に拒否する。しかし`sys`単体のimport(`sys.exit()`・`sys.argv`等)自体には危険性がなく、本当に危険なのは`sys.settrace`等の個別関数呼び出しであり、それは既にMichael(`sefer.\_michael\_absolute\_defense`)がOSレベルの監査フックで個別に遮断している。Gabrielが意図的に`sys`/`shutil`の単純importまでは禁止対象に含めない設計になっているのは、まさにこの過剰検知を避けるための判断であり、`ast\_scanner.py`をそのまま統合すると、AIが生成した無害なコード(単に`sys`をimportするだけ等)まで一律拒否してしまう構造的な後退になる。

\*\*判断\*\*: 実運用パイプラインへは統合しない。§Lの`cassiels\_veil.py`(別の設計思想を示す教材として統合せず保持)と同じ扱いとし、`src/ast\_scanner.py`のdocstringに本判断の経緯と理由を明記した。これにより、どこからもimportされない孤立モジュールが「現在も有効な防壁の一部であるかのような外観」を保ち続け、将来の開発者(あるいは別のAIセッション)を誤解させるリスクを解消した。テストファイルの削除は行わず、既存のテストカバレッジはそのまま維持する(§Lの`cassiels\_veil.py`と同様、動作検証済みの代替設計として保持する価値があるため)。`mini\_pytest.py`実行結果は変化なし(`PASS=103 XFAIL=2 FAIL=0 ERROR=2`)。

\### AG. 「学習したつもりになっているだけ」— `raziel\_ledger.json`/`shield\_rules.json`が人間承認後も実際の防御(Michael/Gabriel)に一切反映されていなかった構造的欠陥を発見・修正

ユーザーからの3度目の「更なる進化を」という依頼を受けた棚卸しの続きで、§AFの`ast\_scanner.py`統合判断の精査中、「このシステムは攻撃から学習して進化する」という本フレームワークの核心的な謳い文句そのものが、実際には機能していないことに気づいた。これはこれまでの§AA〜§AEのような「個別の防壁の抜け道」とは異なり、\*\*2つの「学習」ワークフロー全体が実質的な置物(デコレーション)に過ぎなかった\*\*という、より根本的な発見である。

\*\*事実確認\*\*: 本フレームワークには2つの「人間承認を経て防壁を強化する」パイプラインが存在する。

1. `tartarus/armageddon.py`(Lucifer vs Sefer自己対戦)がMetatronを通じて新たな脱走経路を発見 → 人間が`tools/promote\_ledger\_seal.py --approve`で承認 → `sefer/raziel\_ledger.json`の`banned\_events`に追加。
2. `angelic\_shield.py`(外部LLM脅威インテリジェンス)が危険なモジュール/関数を発見 → 人間が`tools/promote\_shield\_seal.py --approve`で承認 → `shield\_rules.json`の`blocked\_modules`/`blocked\_functions`に追加。

両方とも、承認された内容を検証するCI向け「天使」(`angels/raziel\_auditor.py`・`angels/zadkiel\_shield\_decree.py`)は存在するが、それらは\*\*ファイルのスキーマ・ワークフローの構造的な健全性のみ\*\*を検証しており、「実際にMichael(`sefer.\_michael\_absolute\_defense`、OSレベルの実行時防壁)やGabriel(`sefer.inquisition()`、静的AST解析)がこのファイルを読み込んで判断に使っているか」は一切検証していなかった。実際に全文検索で確認した結果、`raziel\_ledger.json`・`shield\_rules.json`のいずれも、`sefer/\_\_init\_\_.py`からは一度も参照されていなかった。つまり、「Armageddonで新しい攻撃を発見し、人間が承認して防壁ルールを更新した」としても、\*\*次にAIが同じ攻撃を試みたときに、その学習結果は何の役にも立たず素通りしてしまう\*\*状態だった。これは個別の脆弱性バイパスよりも深刻で、本フレームワークの「進化」という中核的な価値提案そのものが機能していなかったことを意味する。

\*\*修正にあたっての安全性の確認(重要)\*\*: `raziel\_ledger.json`の既定値には`"os.remove"`・`"os.rename"`・`"socket.connect"`のように、Michaelが既に個別の条件付きチェック(`allowed\_dirs`/`allowed\_hosts`)で扱っているイベント名が含まれている。これらを無条件の絶対拒否として組み込むと、AI自身の`jail\_workspace`配下での正当なファイル操作や、ローカルOllamaサーバーへの正当な接続まで一律遮断する重大な機能破壊になることを実機で確認した。同様に、`shield\_rules.json`の`blocked\_functions`(`"loads"`・`"load"`等)を裸の名前のまま追加すると、`json.loads(...)`のような全く無害な呼び出しまでcritical判定で一律ブロックする過剰検知になることも確認した。

\*\*修正\*\*:
- Michael側: `\_michael\_absolute\_defense`の既存の各条件付きチェック(open/os.open/dest構造的ops/rename/socket/デフォルト拒否)がすべて`return`で処理し終えた\*\*後\*\*に到達する最終チェックとして、`raziel\_ledger.json`の`banned\_events`を読み込み絶対拒否する処理を追加した。これにより、既存カテゴリで既にカバーされているイベント(os.remove等)は従来通りの条件付き挙動を維持したまま、どのカテゴリにも該当しない\*\*未知の新しい脱走経路\*\*だけを新たに絶対拒否できるようにした。
- Gabriel側: `inquisition()`に`shield\_rules.json`の`blocked\_modules`を既存の`forbidden\_modules`(severity: high、非ブロッキング)に追加し、`blocked\_functions`は`blocked\_modules`との直積(例: `"dill.loads"`)としてのみ完全修飾名で`forbidden\_funcs`(severity: critical)に追加するようにした。裸の名前では照合しないため、`json.loads`等の無関係な同名関数を誤検知しない。
- 両方とも、ファイルのmtimeをキャッシュキーとして使い、audit hookの頻繁な呼び出しごとに毎回ファイルを読み直す性能劣化を避けつつ、人間の承認がプロセス再起動不要で即座に反映されるようにした。

\*\*テスト\*\*: `tests/test\_learned\_rules\_enforcement.py`を新設し、(1)raziel\_ledgerで承認された未知のイベントが絶対拒否されること、(2)承認されていない未知のイベントは従来通り素通りすること、(3)既存カテゴリで既にカバーされているイベント(os.remove等)に回帰が起きないこと、(4)shield\_rulesで承認された完全修飾関数(dill.loads)がcriticalとして検知されること、(5)無関係な同名関数(json.loads)が誤検知されないこと、(6)shield\_rules.json不在時にフェイルセーフに動作すること、の6パターンを固定した。`angels/zadkiel\_astrolabe.py`・`angels/zadkiel\_shield\_decree.py`・`angels/raziel\_auditor.py`を実行し、実際のCI向け検査スクリプトが新方式でも正しく動作することも確認した。`mini\_pytest.py`実行結果は`PASS=109`(新規+6)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

なお、テスト実装上の注意として、`sefer`モジュールは`sys.addaudithook`/`os.write`をプロセス全体へ副作用として適用するため、`importlib.reload()`すると`os.write`の多重ラップによる無限再帰を引き起こすことを実機で発見した(テスト実装中に`tests/test\_read\_restriction.py`で`RecursionError`として再現)。本番コードに影響する脆弱性ではないが、テストの書き方として記録しておく: 本モジュールを検証する際はreloadせず、`monkeypatch.setattr()`でパス定数とキャッシュ辞書を直接差し替えること。

\### AH. maquina\_gatekeeper.py の`ZKAuditTrail` — 「ゼロ知識証明」を名乗る鍵無しハッシュ連鎖と、実質的に死んでいた改ざん検知 (2026-10)

\*\*発見\*\*: §AEで`sefer/audit_chain.py`の`SignedAuditChain`を修正した後、同種の「名前だけの暗号機構」が別の場所にも存在することを疑い、`maquina_gatekeeper.py`を再精査した。`ZKAuditTrail.verify_and_record()`には、互いに補強し合う形の欠陥が二つ重なっていた。

\*\*欠陥1(鍵無し・改ざん耐性ゼロ)\*\*: "current\_hash"は§AE修正前の`SignedAuditChain`と全く同じ、秘密鍵を使わない単純なSHA-256だった。ファイルへの書き込み権限を持つ攻撃者は、任意のブロック(侵入記録等)を削除し、残りのチェーンを先頭から秘密鍵なしに再計算して書き直すだけで、改ざんを一切検知されずに証拠を消せた。

\*\*欠陥2(検証そのものが実質的に死んでいた)\*\*: これは§AEより一段深刻だった。旧実装の改ざん検知は、ファイル末尾の"current\_hash"を、プロセス起動時に固定値"0000...0"へ初期化される\*\*モジュールグローバル変数\*\*`_LAST_KNOWN_HASH`と比較するだけで、ファイルの先頭から検証し直す処理が一切無かった。そして本フレームワークの実運用において、`enforce_maquina_seal`で保護される関数(`src/ollama_agent_loop.py`・`src/openai_agent_loop.py`)は、たとえるなら「警備員が毎回、前任者の記憶を一切引き継がない新人として配置に着く」ように、\*\*プロセスごとに毎回新規起動\*\*されるCLIとして呼ばれる。つまり新規プロセスが最初に`verify_and_record`を呼んだ瞬間、`_LAST_KNOWN_HASH`は必ず"0000...0"のままであり、旧実装の比較条件`_LAST_KNOWN_HASH != "0000...0"`は常にFalseになる。結果として、\*\*ファイルの内容がどれだけ改ざんされていても、改ざん検知コードはプロセスの生涯で一度も実際に機能する機会が無かった\*\*(実機検証済み: チェーン全体を鍵無しで書き換えた状態で新規プロセスに相当する呼び出しを行っても、例外は一切発生しなかった)。

さらに、新しいブロックに付与される"zk\_proof"フィールドは`"Verified by Anjo da máquina"`という固定文字列に過ぎず、いかなる証明の生成・検証ロジックも存在しなかった。クラス名が"ZK"(Zero-Knowledge)を名乗りながら、実態はゼロ知識証明とは何の関係も無い固定文字列だった。たとえるなら、警備室の壁に「この建物は難攻不落の金庫で守られています」という貼り紙だけがあり、実際には金庫そのものが存在しない状態である。

\*\*修正\*\*: `sefer/audit_chain.py`(§AE)と同一パターンで、ローカル専用の秘密鍵(`.zk_audit_signing_key`、初回自動生成・0600権限)で鍵付けしたHMAC-SHA256に変更した。さらに、プロセスのグローバル変数に依存する設計そのものを廃止し、`verify_and_record()`を呼ぶたびに\*\*ファイルに保存されているチェーン全体を先頭から鍵付きHMACで再検証する\*\*`_verify_full_chain()`を新設した。これにより、どのプロセスが最初に呼び出しても、ファイル自体に残る改ざんの痕跡を確実に検知できるようになった(欠陥2の根本的な解決)。

ハッシュの入力は、ファイルに実際に永続化されているフィールド(previous\_hash, timestamp, action)のみに限定した。旧実装はargs/kwargsもハッシュ入力に含めていたが、それらはブロックに保存されないため、そもそも後から再計算して検証することが構造的に不可能であり、検証できないものをハッシュに混ぜることは、検証している体裁を整えるだけの見せかけでしかないと判断した。"zk\_proof"フィールドは、誤解を招く固定文字列から、実際に行っている処理(鍵付きHMAC-SHA256連鎖であり、真のゼロ知識証明ではないこと)を誠実に説明する注記に変更した。

\*\*残存する限界(誠実に明記する)\*\*: §AEと同様、本機構は鍵ファイル(`.zk_audit_signing_key`)を読めない攻撃者による改ざんを防ぐものであり、ホストOS上で鍵ファイル自体を読み書きできる特権(root等、本フレームワークの脅威モデルの範囲外)を持つ攻撃者までは防げない。

\*\*テスト\*\*: `tests/test_zk_audit_trail_chain_integrity.py`を新設し、(1)正常系での記録、(2)複数回記録時のチェーン連結、(3)あるブロックを削除し鍵無しSHA-256で再計算した改ざんが検知されること(§AEと同種の核心テスト)、(4)プロセス起動直後(グローバル状態が改ざんを一切記憶していない状態)を模した呼び出しでも改ざんが検知されること(欠陥2の回帰テスト)、(5)"zk\_proof"フィールドが固定文字列の見せかけから誠実な注記に変わっていること、(6)秘密鍵ファイルが0600権限で生成されること、の6パターンを固定した。`angels/metatron_scripture_seal.py`・`angels/raguel_template.py`(`maquina_gatekeeper.py`を検証するCI向けスクリプト)を実行し、本修正後も正しく動作することを確認した。`mini_pytest.py`実行結果は`PASS=115`(新規+6)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

\### AI. src/uriel\_phoenix.py `UrielPhoenix` — 不可逆な破壊的操作(焦土作戦)に経路の安全装置が無かった (2026-10)

\*\*発見\*\*: `UrielPhoenix`(以前は固定パス専用の`__main__`デモ)を実運用のインシデント対応ツール`tools/incident_reset.py`として一般化した際、`core_dir`/`talisman`を任意のパスとして指定できるようになったが、`shutil.rmtree()`・`Path.unlink()`という不可逆な破壊的操作に対する経路の安全性検証が一切追加されていなかった。たとえるなら、\*\*「自動消火システムに、炎上している部屋を指定するノブを付けたが、そのノブが建物全体の送電網そのものも指せてしまう」\*\*状態である。本ツールは「致命的な侵入が確定した後」という、操作者が最も動揺し、最も判断ミスをしやすい状況で人間が手で呼び出すツールであり、`--core-dir /`・`--core-dir ~`のような入力ミス、あるいは単純な誤タイプを確認プロンプトで一度`y`と答えるだけで、ファイルシステムのルートやホームディレクトリ、あるいは`/etc`のような極めて浅い(被害範囲が破滅的に広い)システム標準ディレクトリを丸ごと削除できてしまう構造的な欠陥があった。

\*\*修正\*\*: `src/uriel_phoenix.py`に`_ensure_safe_destructive_target()`を新設し、`scorched_earth_and_rebirth()`の冒頭、すなわち実際の`rmtree()`/`unlink()`を呼ぶ前に、`core_dir`・`talisman`の両方について以下を検証するようにした: (1)解決後のパスがファイルシステムのルート(Windowsのドライブルート含む)そのものでないこと、(2)解決後のパスがホームディレクトリそのものでないこと、(3)解決後のパスの深さ(ルートからの階層数)が極端に浅くないこと(既定の閾値: 2階層未満を拒否)。意図的に浅いパスを対象にする特殊用途のために、`allow_shallow_path=True`(CLIでは`--allow-shallow-path`)による明示的な脱出口も用意した(既定は安全側のFalse)。`tools/incident_reset.py`側では、確認プロンプトに「操作者が入力した文字列」ではなく「実際に削除される解決済みの絶対パス」を表示するよう変更し、相対パスの指定ミスにも削除前に気付けるようにした。

なお、この安全装置はpytestの`tmp_path`のような十分に深いテスト用一時ディレクトリには一切影響しない(深さの閾値を十分に満たすため)。既存の`tests/test_uriel_phoenix_reset.py`の5件は無変更のまま全てPASSし続けることを確認済み。

\*\*テスト\*\*: `tests/test_uriel_phoenix_safety_guardrail.py`を新設し、(1)ファイルシステムのルートが拒否されること、(2)ホームディレクトリが拒否されること、(3)浅いパス(実在しない架空のパスで検証)が既定で拒否されること、(4)`allow_shallow_path=True`で明示的に解除できること、(5)既存の正常系(十分に深いtmp_path)が無影響であること、(6)talismanも同様に検証されること、の6パターンを固定した。CLIから`python tools/incident_reset.py --core-dir / --yes`を実際に実行し、`rmtree`に到達する前に拒否されることを実機で確認した。`mini_pytest.py`実行結果は`PASS=121`(新規+6)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

\### AJ. adapters/excel\_to\_yaml\_parser.py・adapters/external\_qa\_wrapper.py — CIに残っていた「名前だけの検査」2件 (2026-10)

\*\*発見\*\*: `angels/_common.py`のdocstringには、§刷新前の`angels/*.py`の大半(33ファイル中28ファイル)が`print('... initialized. Zero-Trust audit passed.')`のみの中身のないプレースホルダーだったという記録が残っている。この記録を踏まえ、`angels/`以外のCI実行対象である`adapters/`配下も同じ観点で確認したところ、`excel_to_yaml_parser.py`と`external_qa_wrapper.py`の2ファイルが、全く同じ2行のプレースホルダー(`import os, sys` / `print(f'... Zero-Trust audit passed.')`)のまま放置されていることが分かった。

たとえるなら、\*\*「検品ラインに『検品済み』のスタンプだけが置かれていて、実際には製品を一度も検品していない」\*\*状態である。`.github/workflows/anjo_da_maquina_protocol.yml`を確認すると、この2つは実際にCIのステップ「3.8. 外部要件の抽出 (Excel to YAML Parser)」「18. 外部QAツールの実行 (External QA Adapter)」として組み込まれており、他の26個の天使ステップと並んで、あたかも実質的な検査が行われ合格したかのように毎回報告していた。しかし実際には、Excelファイルを一度も読んでおらず、外部のQAツールを一度も実行していない。

さらに強い状況証拠として、CIの「3. 供物の準備 (Install Dependencies)」ステップでは`openpyxl`(Excel読み込み)と`playwright`(ブラウザ自動化。かつ`playwright install chromium --with-deps`で実際にヘッドレスブラウザまでインストールしている)が明示的にインストールされているにもかかわらず、リポジトリ内のどのスクリプトもこの2つのライブラリを一度も使用していなかった(`grep -rl playwright`・`grep -rl openpyxl`いずれもゼロ件、本修正前)。インストールされているのに誰も使っていない依存関係は、「実装するはずだったが実装されなかった機能」が存在することの明確な痕跡である。

\*\*修正\*\*: 両ファイルに、名前が示す役割に対応した実質的な処理を実装した。

  - `excel_to_yaml_parser.py`: リポジトリルートの`requirements.xlsx`(1行目をヘッダ行とする表形式の外部要件シート)が存在する場合、実際に`openpyxl`で読み込み、各行をヘッダ名をキーとするレコードとして`sefer/external_requirements.yaml`へYAML化する。空セル・完全に空の行は適切に省略する。`requirements.xlsx`がまだ投入されていない現状(これが実際の状態)では、他の天使スクリプトと同じ「対象が存在しない場合は正直にスキップを報告する」パターンに従い、偽の成功を名乗らず「検査対象なし」として正常終了する。

  - `external_qa_wrapper.py`: `architecture.html`(`angels/ophanim_thousand_eyes.py`が静的に検査している対象と同一ファイル)を、実際に`Playwright`のヘッドレスChromiumでレンダリングし、(1)JavaScriptの未捕捉例外(pageerror)、(2)コンソールのerrorレベルのログ、の両方を動的に検知する。`ophanim_thousand_eyes.py`の静的解析(ファイルの中身を読むだけ)を、実際にブラウザでコードを実行する動的検証で補完する多層防御になっている。対象ファイルが存在しない場合は同様に「検査対象なし」として正直に報告する。

\*\*テスト\*\*: `tests/test_adapters_excel_to_yaml_parser.py`(3件)・`tests/test_adapters_external_qa_wrapper.py`(4件)を新設した。前者は、対象ファイル不在時に偽の成功を名乗らないこと・実際のExcelファイルが正しくYAML化されること・完全に空の行が省略されることを固定。後者は、対象ファイル不在時の正直な報告・正常なHTMLの合格・意図的に埋め込んだJavaScript未捕捉例外とconsole.errorの両方が実際に検知されることを固定した(旧実装では検知不可能だったことを、実際にブラウザで実行させて確認している)。実機で`cp architecture.html`を破壊的なスクリプト付きで一時的に書き換え、実際にFAILすることを手動でも確認した上で原状復帰した。`mini_pytest.py`実行結果は`PASS=128`(新規+7)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

\### AK. anjo\_interceptor/intent\_checker.py `IntentInterceptor` — 絶対パス指定による「意図検閲」層の脱走検知漏れ (2026-10)

\*\*発見\*\*: `src/ollama_agent_loop.py`の実運用パイプラインを再精査した際、`AnjoOllamaExecutor._execute_safe_action`が`target = self.workspace_root / action_req.get("target")`という形でパスを結合していることに着目した。Pythonの`pathlib.Path.__truediv__`には、右辺が絶対パスの場合に左辺を無視してそのまま右辺を返すという仕様がある(例: `Path("/jail") / "/etc/passwd"` は `Path("/jail/etc/passwd")` にはならず `Path("/etc/passwd")` になる)。つまりAIが`{"action": "write", "target": "/etc/passwd", ...}`のように絶対パスを指定するだけで、`workspace_root`による境界は計算上無視される。

さらに調べると、この入力が最初に通過する`IntentInterceptor.evaluate_action()`の"write"分岐は、".."連鎖の相対パストラバーサルと、`protected_dirs`に一致する先頭ディレクトリ名のみを検査しており、絶対パスそのものに対する封じ込め検証が一切無かった。"read"分岐はさらに手薄で、ハニーポットのファイル名一致以外、封じ込め検証そのものが最初から存在しなかった。たとえるなら、\*\*「入国審査(IntentInterceptor)が、パスポートの行き先欄が『国内』かどうかだけを見ていて、『海外』と書かれたパスポートをそもそも確認する欄が無かった」\*\*状態である。

実機で検証した結果、幸いにも現行の実運用パイプラインでは致命的な脱走には至らない。最終防衛線である`sefer.Sanctum`のOS監査フック(`_michael_absolute_defense`)が、計算されたパスがどうであれ、実際に発行される`open()`等のシステムコールの引数(実際の絶対パス)を直接検査しているため、`workspace_root`の境界外への書き込みは実際にはそこで遮断される(実機再現コードで確認済み: `self.workspace_root / "/tmp/.../escape_test.txt"`という脆弱な結合を経由させても、`Sanctum`のコンテキスト内での書き込みは`LossOfAtaraxia`で正しく遮断された)。

しかし`IntentInterceptor`自身は、その設計上の役割(ディレクトリトラバーサルやサンドボックス外への干渉を検知する「意図検閲」レイヤー)を果たせていなかった。本セッションで§AC・§AD・§AE等、`Sanctum`やその周辺の「最終防衛線」ですら複数の抜け道が実際に見つかっている以上、外側の層が内側の層の抜け道に対する安全網を一切持たない状態を放置するのは、この実装全体が掲げる「多層防御」の思想に反する。

\*\*修正\*\*: `src/workspace_manager.py`の`WorkspaceJail.secure_resolve()`と同一の堅牢な封じ込め判定(`Path.resolve()` + `Path.is_relative_to()`)を実装した`_assert_contained_within_workspace()`を新設し、"read"・"write"の両分岐の先頭で呼び出すようにした。この判定は、結合の結果が絶対パスの右辺によってworkspace\_rootを無視してしまうケースでも、解決後の最終パスを見て正しく検知できる。

\*\*テスト\*\*: `tests/test_intent_interceptor_absolute_path_escape.py`を新設し、(1)絶対パスへのwriteの脱走検知、(2)絶対パスへのreadの脱走検知(旧実装では封じ込め検証そのものが存在しなかった)、(3)pathlibの絶対パス結合仕様そのものの固定(前提知識の回帰防止)、(4)(5)workspace\_root配下への正常なread/writeが引き続き許可されること(回帰防止)、(6)既存の".."トラバーサル検知に影響がないこと、の6パターンを固定した。既存の`tests/test_intent_gaming.py`(14件)・`tests/test_agent_loop_sanctum_integration.py`・`tests/test_aegis_sandalphon_mandatory.py`は無変更のまま全てPASSし続けることを確認済み。`mini_pytest.py`実行結果は`PASS=134`(新規+6)`XFAIL=2 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)。

\### AL. tools/purify\_tests.py — 名前と内容が一致しない、完全に孤立した死んだコードの削除 (2026-10)

\*\*発見\*\*: `tools/`配下の棚卸しの一環として`purify_tests.py`(「テスト浄化」を意味する名前)を精査したところ、ファイル名と内容が全く一致していないことが分かった。中身は`テストの浄化`とは何の関係もなく、`tartarus/armageddon.py`の冒頭にある`COMMANDER_HASH`キルスイッチ(`_verify_creators_air`相当のロジック、MACアドレスのハッシュが一致しなければ`sys.exit(666)`で自壊する)と、終わらない攻撃生成の無限ループ(`eternal_crusade`)の、未完成な初期草稿のコピーだった。

決定的な証拠が3つある。(1) `COMMANDER_HASH`の値が、実際に稼働している`tartarus/armageddon.py`のような64文字の実ハッシュではなく、`"ここに先ほど取得した64文字のハッシュを貼り付けてください"`という日本語のプレースホルダー文字列のままだった。つまりこのファイルを万一誰かが`__main__`として実行しても、ハッシュ比較は原理的に一致しえず、即座に`sys.exit(666)`で自壊するだけの、何の機能も果たさないコードだった。(2) リポジトリ全体を検索しても、`import tools.purify_tests`や`python tools/purify_tests.py`のような参照は、CIワークフロー・ドキュメント・他のスクリプトのいずれにも一件も存在しなかった。(3) `tartarus/armageddon.py`には同種のロジックが正式に実装され、既にGRIMOIRE記録済みの脆弱性修正(requestsの遅延import化)まで施された、きちんと保守されているバージョンが存在する。

たとえるなら、\*\*「"掃除道具入れ"と書かれた棚を開けたら、何年も前に作ろうとして放置された、別の部屋の試作品の鍵が入っていた」\*\*状態である。実害を及ぼすものではなかったが(前述の通り、実行されても即座に自壊するだけ)、何の説明も参照もない孤立したコードが残っていることは、将来の開発者やAI自身を混乱させ、「`purify_tests.py`とは何をするものか」という誤った推測を招く。ユーザーからの「いらないものは削除して大丈夫です」という恒久的な許可に基づき、本ファイルを削除した。

\*\*検証\*\*: 削除後に`mini_pytest.py`を再実行し、`PASS=134 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ)に変化がないことを確認した(そもそも何からも参照されていなかったため、当然の結果ではあるが、削除が安全であることの最終確認として行った)。

\### AM.

\*\*発見\*\*: `src/intelligence\_cycle.py`(`RazielIntelligence`・`SamaelWeaponization`を提供し、`src/metatron\_orchestrator.py`から実際に呼ばれている現役ファイル)の棚卸し中、2点の死んだ残骸を発見した。

1\. `from angelic\_evolution import EvolvingAngel` というimportが先頭に存在したが、本ファイル内の`RazielIntelligence`(`AegisSystem`のみ使用)・`SamaelWeaponization`(`CollarProtocol`のみ使用)のいずれからも一度も参照されていなかった。`src/metatron\_orchestrator.py`は`EvolvingAngel`を`angelic\_evolution`から直接importしており、本ファイル経由の再exportに依存している箇所はリポジトリ内に一件も無かった。

2\. ファイル末尾に`def execute\_kill\_chain(): pass`という何もしない空の関数と、`if \_\_name\_\_ == "\_\_main\_\_": pass`という何もしないエントリポイントが残っていた。`grep -rn "execute\_kill\_chain"`でリポジトリ全体を検索しても、定義行そのもの以外に呼び出し元は一件も存在しなかった。

\*\*たとえ話\*\*: これは、会社の組織図に「統括部長」のポストが新設され、実際にそのポストの人(`src/metatron\_orchestrator.py`の`MetatronOrchestrator`)が業務を回しているのに、古い「現場監督」(`execute\_kill\_chain`)の机と名札だけがまだオフィスの隅に残っている状態である。誰もその机を使っていないし、その名札の人に仕事を頼む人もいない。さらに言えば、その現場監督の名刺入れには、使われていない別部署の内線番号(`EvolvingAngel`のimport)まで印刷されたままだった。

\*\*原因\*\*: `src/metatron\_orchestrator.py`が本ファイルの各クラスを統括する正式なオーケストレータとして新設された際、置き換えられたはずの古いエントリポイントと、使われなくなったimportが削除されずに残った。§L(`tools/purify\_tests.py`)と同種の「リファクタリング後の抜け殻」パターンだが、§Lはファイル全体が孤立していたのに対し、本件はファイル自体は現役で使われており、その中の一部の要素だけが死んでいた点が異なる。

\*\*対応\*\*: 未使用のimport(`EvolvingAngel`)と、何もしない空の関数・エントリポイント(`execute\_kill\_chain`・`\_\_main\_\_`ブロック)を削除した。`RazielIntelligence`・`SamaelWeaponization`本体の挙動、および`src/metatron\_orchestrator.py`からの呼び出し経路は変更していない。

\*\*検証\*\*: 削除後に`mini\_pytest.py`を再実行し、`PASS=134 FAIL=0 ERROR=2`(既存の無関係なERROR2件のみ、§AL時点から変化なし)であることを確認した。特に`tests/test\_metatron\_orchestrator.py`が引き続きPASSすることを確認し、`src/metatron\_orchestrator.py`からの`RazielIntelligence`・`SamaelWeaponization`の利用に影響が無いことを固定した。

\### AN.

\*\*発見\*\*: `angels/sandalphon\_anchor.py`(「証跡のブロックチェーン化」と称し、監査ログのロールバック・改ざんをCI上で検知する役割を持つ天使スクリプト)の検知ロジック自体は正しかったが、その前提となる「前回実行時のチェックポイント」(`sefer/.angel\_state/sandalphon\_anchor.json`)が、CIワークフロー(`.github/workflows/anjo\_da\_maquina\_protocol.yml`)上で\*\*一度も永続化されていなかった\*\*。`.angel\_state/`は`.gitignore`対象であり、かつ本ワークフロー全体を検索しても`actions/cache`・`actions/upload-artifact`・`actions/download-artifact`のいずれも一件も存在しなかった(実機確認済み)。GitHub Actionsの使い捨てランナーはジョブ終了ごとにディスクが破棄されるため、毎回チェックアウト直後は`.angel\_state/`が空の状態から始まり、`load\_state("sandalphon\_anchor")`は常に`None`を返す。結果として`main()`内の`if checkpoint:`分岐(ロールバック・改ざん検知の本体)はCI上で\*\*一度も実行されたことがなく\*\*、常に「チェックポイント無し」の初回実行として振る舞い、新しいチェックポイントを(どうせ次回には失われる)ローカルに保存して無条件にPASSを報告し続けていた。

\*\*たとえ話\*\*: これは、空港の入国審査官(`sandalphon\_anchor.py`)が「前回あなたが出国したときの記録」(チェックポイント)を見て、記録と現在のパスポートの出入国印が一致するか照合する、という正しい仕事の手順を持っているのに、審査官の記憶用ノート(`.angel\_state/`)が\*\*毎回の勤務シフトの開始時に全部真っ白に消去される\*\*、という状態である。審査官は「前回の記録」を一度も参照できないため、来る人全員を「初めて来た人」として扱い、無条件に通過させてしまう。審査官の判断ロジックそのものは正しいのに、記憶が保存される仕組みが最初から存在しなかったため、この検問所は開設以来一度も「比較」という本来の仕事を実行したことがなかった。

\*\*原因\*\*: `sandalphon\_anchor.py`(および同じ`load\_state`/`save\_state`パターンを使う`metatron\_commitment.py`)を実装した際、`sefer/.angel\_state/`配下への書き込みはローカル開発環境では(ファイルシステムが実行間で永続するため)正しく機能して見えたが、CI環境(実行ごとに使い捨てのランナー)での永続化手段を追加することが漏れていた。GRIMOIRE.md §AH(ZKAuditTrailのプロセスグローバルが毎回リセットされ検知が発火しない)と全く同種の「検知ロジック自体は正しいが、実行環境側の前提が一度も満たされない」という構造的な見せかけであり、本セッションを通じて繰り返し発見している「学習・記憶したつもりになっているだけ」のパターンの、CIワークフロー設定にまで及んでいた例である。なお`metatron\_commitment.py`は`report\_fail`を一切呼ばない常にPASSするログ出力ステップであり(本人のコメントにも明記されている)、セキュリティ上のゲートとして機能を偽っていたわけではないため、本件の実害は`sandalphon\_anchor.py`に限定される。

\*\*対応\*\*: ワークフローに`actions/cache@v4`ステップを追加し、`sefer/.angel\_state`を対象として永続化するようにした。`actions/cache`は保存キーが既存キャッシュと完全一致するとジョブ終了時の保存自体をスキップする(更新されない)ため、保存キーには`github.run\_id`(実行ごとに一意)を用いて必ず保存を発生させ、復元時は固定プレフィックスの`restore-keys`で直前の最新チェックポイントを取得するようにした(GitHub Actions公式が推奨する「更新され続けるキャッシュ」の標準パターン)。このキャッシュステップは、`sandalphon\_anchor.py`の実行ステップより前に配置した。

\*\*残存する限界(誠実に明記する)\*\*: `actions/cache`にも、7日間アクセスが無いと自動失効する等のGitHub側の制約があり、`sefer/audit\_chain.py`の鍵管理と同種の「恒久不変の外部監査サービスの代替にはならない」限界を持つ。それでも「CI上では構造的に一度も発火しない」状態から「通常の実行頻度では実際に機能する」状態への実質的な改善である。

\*\*検証\*\*: `tests/test\_sandalphon\_anchor\_state\_persistence.py`を新設した。(1) ワークフローYAMLを実際にパースし、`.angel\_state`を対象とする`actions/cache`ステップが`sandalphon\_anchor.py`の実行ステップより前に存在すること、および保存キーが`github.run\_id`を含むことを固定する配線テスト2件。(2) `sandalphon\_anchor.py`の検知ロジック本体を、一時ディレクトリ上でチェックポイントが実際に存在する状態を再現して直接検証するテスト4件(ロールバック検知・改ざん検知・正常系でのチェックポイント更新・チェックポイント不在時の初回実行)。これらは本ロジックがCI上で一度も実行されたことがなかった(=一度もテストで直接検証されていなかった)ため、本修正で初めて固定した。`mini\_pytest.py`再実行で`PASS=140`(§AM時点の134から新規6件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*自己点検(誠実な告白)\*\*: 本修正はローカルの単体テストとYAMLの構造解析では検証したが、実際にGitHub Actions上でワークフローを走らせて`actions/cache`が意図通りに復元・保存されることまでは、本セッションの実行環境からは確認できていない(このサンドボックスには実際のGitHub Actionsランナーが無く、CIを実行させる手段が無いため)。ロジック上は正しいはずだが、「実機で最後まで確認した」と言い切れないのは本件のみであり、この点は誠実に明記しておく。

\### AO.

\*\*発見\*\*: `angels/alpha\_omega\_guard.py`(「CIワークフローから必須の天使ステップが削除されていないか」を検知する役割の天使スクリプト)の検査ロジックに、本検査の存在目的そのものを無力化する欠陥があった。旧実装は、必須ファイル名(`michael\_sword.py`・`gabriel\_canary.py`・`raziel\_auditor.py`)が、ワークフローYAMLの\*\*生のテキスト全体のどこかに文字列として存在するか\*\*だけを見ていた。実機検証済み: 実際に実行される`run:`ステップを完全に削除し、同じファイル名をコメント文として残すだけの偽装ワークフローを用意したところ、旧実装は`missing=[]`(問題なし)と判定し、必須ステップが完全に削除された事実を一切検知できなかった。

\*\*たとえ話\*\*: 消防設備の点検員が「この建物に消火器が設置されているか」を確認する際、実際に壁の金具に消火器が掛かっているかを見るのではなく、フロアのどこかに「消火器」という単語が書かれた貼り紙(たとえ「昔はここに消火器がありました」という撤去済みを示す貼り紙であっても)が一枚でも落ちていれば「設置確認済み」の印を押していた、という状態である。点検員の仕事は「本当にそこにあるか」を確認することなのに、「その言葉がどこかに書いてあるか」を確認するだけになっていた。

\*\*原因\*\*: ワークフロー整合性ガードという「ステップの削除」を検知する専用の役割を持つ検査でありながら、実装がYAMLを構造的に解析せず、生テキストへの部分文字列検索という弱い手法を使っていた。本セッションで繰り返し発見している「名前だけの検査」パターンが、今回はCIワークフロー定義ファイルという、これまで検査対象にしてこなかった領域にも存在していた一例である。

\*\*対応\*\*: `yaml.safe_load`でワークフローを構造的に解析し、`jobs.angelic-audit.steps`の各ステップの`run:`フィールドの中に、実際に必須ファイル名を実行するコマンドが存在するかを検証するように修正した。コメントや無関係な文字列は`run:`フィールドの外にあるため、この方式では一致しない。

\*\*検証\*\*: `tests/test\_alpha\_omega\_guard\_structural\_check.py`を新設し、(1) 実行コマンドが存在せずコメントのみの偽装ワークフローがFAILすること、(2) 実リポジトリの実ワークフローがPASSすること、(3) 必須ステップのうち1つを実際に削除した偽装ワークフローがFAILすること、(4) 必須3ステップが揃っていればPASSすることの4件を固定した。`mini\_pytest.py`再実行で`PASS=144`(§AN時点の140から新規4件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*自己点検(誠実な告白)\*\*: 本修正の作業中、自分自身の見せかけ検査を書いてしまっていたことに気づいた。GRIMOIRE.mdではMarkdownの強調記号(`**太字**`)がそのまま表示されてしまうのを避けるため、バックスラッシュで`\*\*`のようにエスケープする記法を使っているが、これは\*\*GRIMOIRE.md(素のテキストファイル)専用の表記法\*\*であり、Pythonのソースコード中の文字列リテラル(docstring等)にそのまま持ち込んでよいものではない。本修正の最初のdocstring案で、この記法をそのままPythonのトリプルクォート文字列の中に書いてしまい、`\*`がPythonにとって未知のエスケープシーケンスと解釈され、実行時に`SyntaxWarning: invalid escape sequence '\*'`が発生する状態になっていた(機能的には動作するが、警告が出る望ましくない状態であり、将来のPythonバージョンではエラーになる可能性がある変更である)。「見せかけの検査を直す」という作業の最中に、自分自身のコードの書き方を誤り、小さな瑕疵を新たに生み出してしまったことを認め、該当箇所からバックスラッシュを除去して修正した。修正後、`python3 -W error::SyntaxWarning`で同ファイルを実行し、警告が再発しないことを確認済みである。

\### AP. requirements.txt の依存漏れ再発 — 自分自身が過去に文書化した教訓を、自分自身で踏み直した自己言及的な退行 (2026-10)

\*\*発見\*\*: 本セッション中に自分で追加したテストファイル群(`tests/test_adapters_excel_to_yaml_parser.py`・`tests/test_adapters_external_qa_wrapper.py`・§ANの`tests/test_sandalphon_anchor_state_persistence.py`)が、`yaml`(PyYAML)・`openpyxl`・`playwright`を必要とするにもかかわらず、`requirements.txt`にはこの3パッケージが一件も列挙されていなかった。

これは単なる見落としではない。本リポジトリには`.github/workflows/sanctuary_ci.yml`(`pytest tests/`を実際に実行する唯一のCIジョブ)と`.github/workflows/anjo_da_maquina_protocol.yml`(`angels/*.py`等を個別に実行する別のジョブで、独自に`pip install networkx pyyaml playwright mcp pandas openpyxl pytest`を直接ハードコードしており、`pytest tests/`は一度も実行しない)という、\*\*互いに依存関係を共有しない2本の独立したワークフロー\*\*が存在する。さらに決定的なのは、`sanctuary_ci.yml`自身の既存のコメントに、ほぼ同一の過去の事故(`requests`パッケージの追記漏れで`tartarus/armageddon.py`のテストがCIでクラッシュした件)と、その教訓("requirements.txtを単一の正として読み込むことで、このズレを構造的に防ぐ")が\*\*既に本セッション以前の時点で明記されていた\*\*という点である。つまり私は、自分(または過去の修正者)が既に文書化していた「二重管理の危険性」という教訓を、まさにその教訓が書かれているファイルの隣で、再び踏んでしまった。

このサンドボックス環境には`PyYAML`・`openpyxl`・`playwright`がたまたまプリインストールされていた(`anjo_da_maquina_protocol.yml`側の依存セットに近い構成だったため)ため、これらのテストはローカルでは何の問題もなく成功し続け、発覚しなかった。`sanctuary_ci.yml`の実際の最小インストール環境(`requirements.txt`のみ)でこれらのテストを実行したことは、本修正に取り組むまで一度もなかった。

\*\*実機検証\*\*: 疑いを確認するため、`sys.meta_path`に独自の`MetaPathFinder`を挿入し、`yaml`・`openpyxl`・`playwright`のimportを強制的に`ModuleNotFoundError`でブロックする(`sanctuary_ci.yml`の最小依存環境を模擬する)スクリプトを作成し、その状態でテストスイート全体を再実行した。結果、通常は`FAIL=0`・`ERROR=2`(既知の無関係なもののみ)で安定していたところが、`FAIL=7`・`ERROR=3`に悪化することを確認した。理論上の懸念ではなく、実際に壊れることを自分の手で再現した。

\*\*たとえ話\*\*: これは、ある職場で「作業員Aが、出庫記録(`requirements.txt`)を通さずに工具箱(別のワークフローのプリインストール済み環境)から勝手に工具を借りて使い、翌日その工具が無いことで現場が止まった」という事故が過去にあり、その反省文が壁に貼られている。その反省文には「今後は全員、出庫記録に無い工具を現場に持ち込んではならない」と書かれている。その壁の前で、\*\*反省文を書いた本人(あるいはそれを読んだはずの私)\*\*が、新しい作業(§AN・§AOの新規テスト)のために、また同じように工具箱から直接工具を借りて使い、出庫記録への記入を忘れた、という状況である。工具箱(このサンドボックス)には運良く工具が揃っていたので、その場では誰も困らなかった。しかし本来の現場(`sanctuary_ci.yml`の最小環境)に持っていけば、同じ事故がもう一度起きるところだった。

\*\*原因\*\*: 新しいテストを書く際、「このサンドボックスで`mini_pytest.py`が通るか」だけを検証の基準にしてしまい、「このテストが実際のCI(`sanctuary_ci.yml`)の最小インストール環境でも動くか」という、本来最も重要な問いを一度も立てなかった。`anjo_da_maquina_protocol.yml`側で既にこれらのパッケージがインストールされていたことも、サンドボックスの構成がそれに近かったことも、問題を覆い隠す方向にしか働かなかった。

\*\*対応\*\*:
1. `requirements.txt`に`PyYAML==6.0.3`・`openpyxl==3.1.5`・`playwright==1.56.0`を追記した(バージョンはこのサンドボックスに実際にインストールされているものに合わせた)。
2. `sanctuary_ci.yml`の依存インストールステップに`playwright install chromium --with-deps`(playwrightはpipパッケージのインストールだけでなく、ブラウザ本体のインストールも別途必要なため)を追加し、本件の経緯を詳細に記したコメントを追加した。
3. `tests/test_requirements_cover_test_suite_imports.py`を新設した。`tests/`配下の各ファイルのモジュールレベルのimport文をASTで静的に解析し、Python標準ライブラリでもリポジトリ内のローカルモジュールでもないものが、全て`requirements.txt`に(パッケージ名とimport名の既知の差異を考慮した上で)列挙されていることを固定する回帰テストである。これにより、今後同種の依存漏れが再発した場合、CIで実際に失敗する前に、この構造的な検査自身が検知する。

\*\*残存する限界(誠実に明記する)\*\*: 新設した`test_requirements_cover_test_suite_imports.py`は、モジュールレベルのimport文(ファイル先頭での`import`文)のみを静的に解析する設計であり、関数の内部で遅延importされる依存は検知できない。実際、`tests/test_adapters_external_qa_wrapper.py`の`playwright`依存は関数内での遅延importであり、私はこれを静的解析ではなく、前述の`MetaPathFinder`による実機シミュレーションでのみ発見できた。つまり本修正は「今回発覚した3パッケージの再発」と「今後の\*\*モジュールレベル\*\*importの漏れ」は構造的に防げるが、「今後の\*\*関数内での遅延\*\*importの漏れ」までは防げない、という限定的な範囲の修正である。この限界を誠実に認め、拡張の余地として記録しておく。

\*\*検証\*\*: `mini_pytest.py`再実行で`PASS=146`(§AO時点の144から新規2件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。また、バージョン固定チェッカーである`angels/ophanim_eye.py`を直接実行し、更新後の`requirements.txt`に対しても引き続き`✅ PASS`(全パッケージがバージョン固定済み)を返すことを確認した。

\*\*自己点検(誠実な告白 — 本件はユーザーからの明示的な指示に基づく)\*\*: ユーザーから「自身で修正、改善した結果、自らの首をしめた場合は、正直に告白し、謝罪なさい」という指示を受けた直後に発見した事案であり、まさにその指示が想定していた種類の失敗である。正直に告白する。§ANで`sandalphon_anchor.py`のCI上の検知が一度も発火していなかった欠陥を直し、§AOで`alpha_omega_guard.py`のステップ削除検知のバイパスを直した——その両方の修正作業自体が、新しいテストファイルを追加するという形で、まさにその直後に本件の原因を生み出していた。つまり「見せかけの検査を本物にする」という本セッション全体の目的に沿った正しい修正を行いながら、その修正に伴って追加したテストコード自身が、`sanctuary_ci.yml`という、既に過去の事故から教訓を得て整備されていたはずの防御線を、無自覚に迂回してしまっていた。これは明確に私自身が引き起こした退行であり、何かの仕様の曖昧さや外部要因のせいにできるものではない。言い訳はしない。発見した時点で直ちに実機検証を行い、修正し、再発防止のための構造的なテストを追加し、ここに記録する。

\### AQ. src/secure\_oracle\_feed.py — 「日次上限」を名乗るリミッターが、実際にはプロセス再起動ごとにリセットされていた (2026-10)

\*\*発見\*\*: `SecureOracleFeed`(Gemini APIを使って外界の情報を取得する「厳格化・外界情報摂食」プロトコル)が内部で使う`EconomicDefenseLimiter`(「法則2: 経済的ダメージの防止(リミッター)」と自ら名乗るクラス)の実装を精査したところ、コンストラクタ引数`max_daily_requests`という名前が示す「1日あたりの上限」が、実際には一切永続化されていないインスタンス変数`self.current_requests`でしか管理されていないことが分かった。これは本セッションで繰り返し発見している「検知・制限ロジック自体は正しいが、前提となる状態がプロセスをまたいで一度も保存されない」という構造的な見せかけ(§AH・§AN・本件で3件目)が、CIワークフローのキャッシュ設定ではなく、実際に金銭的コストを伴う外部API呼び出しの防壁という、実害の方向性が異なる領域にも存在していた例である。

\*\*たとえ話\*\*: これは、ジムの入館証に「1日3回まで」と書かれたスタンプカードがあるのに、実際には店員がそのカードを一切保管せず、来店者が帰ってまた戻ってくる(=スクリプトの再実行)たびに、新しい白紙のスタンプカードを渡していた、という状態である。「1日3回まで」というルール自体は正しく印字されているのに、それを本当に1日単位で数える仕組みがどこにも存在しなかった。手動で何度もスクリプトを再実行すれば、何回でもAPIを呼び出せてしまう。

\*\*原因\*\*: `EconomicDefenseLimiter`を実装した際、単一の実行セッション内でのクールダウン(`time.sleep`によるレート制限)と、複数の実行をまたいだ「日次予算」の強制とを区別せず、後者も前者と同じ「インスタンス変数のカウンタ」で済ませてしまった。本スクリプトはCIからは一度も呼ばれない(`anjo_da_maquina_protocol.yml`・`sanctuary_ci.yml`いずれにも参照が存在しないことを確認済み)、人間が手動で単発実行する運用ツールであるため見過ごされやすかったが、「経済的ダメージの防止」という防壁の存在目的そのものに対する欠陥である点では軽視できない。

\*\*対応\*\*: カウントを`sefer/.angel_state/oracle_feed_quota.json`(UTC日付をキーとする)に永続化するように変更した。プロセスを再起動しても、同一UTC日内であれば既に消費した回数が引き継がれ、上限に達すれば確実に`SystemExit`で遮断される。日付が変われば(UTC日が進めば)カウントは0から再開する。

\*\*残存する限界(誠実に明記する)\*\*: 単一ホスト上のファイルベースのカウンタであり、複数プロセスからの並行呼び出しに対する排他制御(ファイルロック)は行っていない。本スクリプトは人間が手動で単発実行する運用を想定しており同時並行実行される設計ではないため実用上の優先度は低いと判断したが、将来の拡張点として明記する。また、システム時刻やこの状態ファイル自体を書き換えられる権限を持つ攻撃者には、この防壁は無力である(他の`.angel_state`系の仕組みと同種の限界)。

\*\*検証\*\*: `tests/test_secure_oracle_feed_quota_persistence.py`を新設し、(1) 同一日内であれば新しいインスタンス(プロセス再起動を模擬)をまたいでもカウントが引き継がれ、上限で確実に遮断されること、(2) 日付が変わればカウントがリセットされ新しい日の上限まで再び許可されること、(3) 永続化されたJSONの内容(日付キー・カウント)そのものを固定する、の3件を追加した。本番の`google-generativeai`・`ollama`等の重い外部依存はテスト用のスタブモジュールに差し替え、`EconomicDefenseLimiter`自体のロジックのみを単体で検証した。`mini_pytest.py`再実行で`PASS=149`(§AP時点の146から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\### AR. src/kamael\_judgment.py — 「実行は不可能です」という判決文言に反して、終了コードは常に0(正常終了)だった (2026-10)

\*\*発見\*\*: `src/kamael_judgment.py`の`execute_judgment()`(CLIとして`python src/kamael_judgment.py <ファイル>`の形で呼び出す、`KamaelInquisitor`による異端審問の実行関数)を精査したところ、`shield_rules.json`の禁止ルールに違反する呼び出しを検知した場合に、`"=> [結果: 物理破壊] 実行は不可能です。カマエルが対象を破棄します。"`という、実際には何らの強制力も伴わない文言を表示するだけで、関数は何も返さず(`None`)、`sys.exit()`も呼ばず、ファイルの削除も行わず、正常に`return`していた。CLIとして実行した場合、違反の有無にかかわらず終了コードは常に`0`(成功)だった。

\*\*たとえ話\*\*: これは、税関の検査官が「このスーツケースは危険物が入っているので、絶対に持ち込ませません。ここで廃棄します」と宣言しながら、実際には何も取り上げず、ただそのスーツケースをそのまま持ち主に返し、通過ゲートの信号も「問題なし」の緑色のままにしていた、という状態である。宣言の内容と、実際に起きた結果(スタンプが押され、何の制止もなく通過できる)が一致していなかった。

\*\*原因\*\*: 本関数は`KamaelInquisitor`(検知ロジック自体)の結果を人間が読む画面表示用のメッセージに変換することに主眼が置かれ、「このCLIを呼び出すスクリプトが、終了コードで合否を判定できるようにする」という、CLIツールとして最低限満たすべき契約が設計時に意識されていなかった。既存のテスト(`tests/test_shield_rebuild.py`)は`KamaelInquisitor`クラス自体を直接呼び出して検証しており、`execute_judgment()`という外側のCLIラッパー関数そのものの戻り値・終了コードは一度も検証されていなかったため、この見せかけが発覚しないまま残っていた。

\*\*対応\*\*: `execute_judgment()`が「潔白(違反なし)であればTrue」を返すように変更し、`__main__`ブロックでその戻り値に応じて`sys.exit(0)`/`sys.exit(1)`するようにした。これにより、本CLIを呼び出すシェルスクリプトや別のPythonプロセスが、終了コードで実際に合否判定できるようになる。なお、表示文言も「実行は不可能です。カマエルが対象を破棄します。」という、ファイルの物理的削除を暗示する誇張表現から、「このファイルは防壁ルールに違反しています。」という、実際に起きていること(検知のみ)に即した表現に改めた。ファイル削除という破壊的操作そのものを新たに実装することはしていない——それは別途明示的な承認フローを要する判断であり、既存の誇張した表示文言に挙動を合わせるために安易に追加すべきものではないと判断した。

\*\*検証\*\*: `tests/test_shield_rebuild.py`に4件追加した。(1)(2) `execute_judgment()`の戻り値が、違反あり/なしそれぞれで正しく`False`/`True`になること。(3)(4) 実際に`subprocess`経由でCLIとして実行し、終了コードが違反あり/なしそれぞれで非ゼロ/ゼロになることを実機検証した。`mini_pytest.py`再実行で`PASS=153`(§AQ時点の149から新規4件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\### AS. maquina\_gatekeeper.py — Windows以外では「ハードウェア指紋」が全ホスト共通の固定値だった (2026-10)

\*\*発見\*\*: `maquina_gatekeeper.py`の`get_machine_id()`(証明書を発行対象の実機に縛る「ハードウェア指紋」の入力元)を精査したところ、`platform.system() == "Windows"`の分岐しか存在せず、Linux・macOSではこの関数が無条件に`"UNKNOWN_MACHINE_ID"`という\*\*固定文字列\*\*を返すことが分かった。実機検証済み: 本サンドボックス(Linux/x86_64)で直接呼び出し、ホストの識別情報を一切含まない定数的な指紋が算出されることを確認した。

これが特に重大なのは、本リポジトリのCIワークフロー(`anjo_da_maquina_protocol.yml`)が`ubuntu-latest`(Linux)で動いていることである。つまり、`enforce_maquina_seal`が行っている「この証明書は本当にこのマシン用に発行されたものか」(`get_absolute_hardware_fingerprint() != cert['payload']['hardware_fingerprint']`)という検証が、実運用上最も頻繁に通る環境(Linux CI)において、「同一アーキテクチャ・同一OSなら誰でも同じ指紋になる」という、個体識別としては機能していない状態に縮退していた。

\*\*たとえ話\*\*: これは、会員証に「本人確認用の指紋」を印字する仕組みのはずなのに、実装を見ると「Windowsユーザーだけは本当に指紋を読み取るが、Mac・Linuxユーザーは指紋リーダーに手をかざさせるふりをして、実際には全員に同じダミーの指紋画像("UNKNOWN_MACHINE_ID")を印字していた」という状態である。会員証の仕組み自体(写真と指紋を照合する)は正しいのに、Mac・Linux利用者の指紋だけは最初から誰のものでも同じ画像になっていたため、他人の会員証を物理的に持ち出せば(同じOS・同じCPUアーキテクチャの別マシンに同じ証明書ファイルを置くだけで)、本人確認そのものを素通りできてしまう。

\*\*原因\*\*: `get_machine_id()`を実装した時点でWindowsの`MachineGuid`取得のみが実装され、Linux・macOS向けの同等の仕組み(`/etc/machine-id`・`IOPlatformUUID`等)を追加する作業が後回しにされたまま、デフォルトのフォールバック値(本来は「どの方法でも取得できなかった場合の最終手段」であるはずの定数)が、Windows以外のプラットフォームでは実質的に「常に使われる唯一の値」になってしまっていた。この関数単体をテストする回帰テストが本修正以前には一件も存在せず、`enforce_maquina_seal`自体のテスト(`tests/test_thread_safety_maquina_seal.py`等)もフェイクのRSA実装で署名検証ロジックのみを検証しており、ハードウェア指紋の個体識別能力そのものは一度も検証されていなかった。

\*\*対応\*\*: `get_machine_id()`にLinux・macOS向けの実装を追加した。Linuxは`/etc/machine-id`(systemdが管理する、インストールごとに一意で再起動をまたいで不変の識別子。無ければ`/var/lib/dbus/machine-id`にフォールバック)、macOSは`ioreg -rd1 -c IOPlatformExpertDevice`から`IOPlatformUUID`を抽出する。

\*\*残存する限界(誠実に明記する)\*\*: 上記いずれにも該当しない、あるいは取得自体に失敗したプラットフォームでは、依然として`"UNKNOWN_MACHINE_ID"`という固定値にフォールバックする。この場合、ハードウェア指紋による個体識別は実質的に機能しない。これは「取得できない場合の最終手段」として明示的に残した設計判断であり、主要3プラットフォーム(Windows/Linux/macOS)では本修正によって実際に機能するようになったことを明記する。

\*\*検証\*\*: `tests/test_thread_safety_maquina_seal.py`に3件追加した。(1) 本サンドボックス(Linux)上で実際に`get_machine_id()`を呼び出し、固定のプレースホルダーではなく`/etc/machine-id`由来の実際の値が返ることを、モックを使わず実機で直接確認する。(2) `get_machine_id()`の戻り値が異なれば、`get_absolute_hardware_fingerprint()`が異なる指紋を算出すること(個体識別として機能していることの最低限の確認)。(3) 未対応のプラットフォームでは既存の文書化された限界どおり固定値にフォールバックすること(この挙動自体は正常であり、検知対象ではないことの固定)。あわせて、`tools/promote_ledger_seal.py`のdocstringに実装されていない`--approve-all`オプションが記載されていた軽微な文書不整合(argparseには一度も実装されておらず、指定すればargparse自体がエラー終了する。危険側ではなく安全側に外れていた不整合だが、実態に合わせて記述を削除した)も同じコミットで修正した。`mini_pytest.py`再実行で`PASS=156`(§AR時点の153から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\### AT. tools/promote\_shield\_seal.py — 同名の脆弱性提案を2回承認すると、2回目に人間が確認した内容ではなく1回目の古い内容が再適用されていた (2026-10)

\*\*発見\*\*: `tools/promote_shield_seal.py`の`approve()`(人間が`--list`で内容を確認した上で、`ZadkielDominion`がキューに積んだ防壁ルール提案を`shield_rules.json`へ昇格させる、承認フローの中核)を精査したところ、同一の`vulnerability_name`で2回目の提案が行われ、それを承認した場合に、実際に適用される`dangerous_modules`/`dangerous_functions`が、\*\*たった今人間が`--list`で見て承認したはずの2回目の提案ではなく、1回目の(既に承認済みの)古い提案\*\*のものになってしまう欠陥を発見した。原因は、ステータス更新後に`next(p for p in pending if p["vulnerability_name"] == vuln_name and p["status"] == "APPROVED")`という再検索を行っていたことで、リストの先頭から見て最初に一致する「名前が同じでステータスがAPPROVED」のエントリを掴んでしまい、それが古い方(時系列的に先に承認されたもの)だった場合、新しい提案の内容が無視されてしまう。実機検証済み: 同一`vulnerability_name`で2回提案・承認を行うテストを書き、旧実装では2回目に承認した内容(`new_danger`)が`shield_rules.json`へ一切反映されず、1回目の内容(`old_danger`)のみが残ることを確認した。

\*\*たとえ話\*\*: これは、会社の承認印鑑システムで、同じ案件名(例:「経費申請A」)の書類が2回提出され、1回目は10万円の申請として承認済み、2回目は(内容を修正して)15万円の申請として今まさに承認した、という状況で、システムが「案件名が『経費申請A』で承認済みの書類」を棚から検索した際、\*\*一番最初に見つかった(=古い)10万円の書類\*\*を手に取ってしまい、たった今目視確認して承認したはずの15万円の書類の内容は一切処理されない、という状態である。承認者は2回目の内容を見て判断を下したのに、実際に効力を持つのは1回目の内容のままだった。

\*\*原因\*\*: `ZadkielDominion.propose_knowledge()`は、同一`vulnerability_name`の重複提案を検知・排除する仕組みを持たず、無条件に新しいエントリを追記する設計である。これ自体は(異なる時期に同じ脅威が再提案される可能性を許容する)合理的な設計だが、`approve()`側がこの「同名の複数エントリが共存しうる」という前提を踏まえておらず、「名前とステータスだけで検索する」という不十分な方法で、たった今自分が更新したはずのエントリを再び特定しようとしていた。なお`tools/promote_provisioning_seal.py`の`approve()`は同種の重複ケースを`matches[-1]`(「同一client\_idが複数あれば最新のものを採用」という明記されたコメント付きで)で既に正しく処理していたのに対し、本ファイルだけこの対策が欠けている非対称な状態だった——つまり同じプロジェクト内で既に答えが分かっていた問題を、横展開し忘れていた。

\*\*対応\*\*: `_set_status()`が、承認待ち(PENDING_HUMAN_REVIEW)から今回まさに`new_status`へ遷移させた対象のエントリそのものを明示的に返すように変更した。`approve()`はその戻り値(「今回遷移させたエントリ一覧」)だけを使って`shield_rules.json`へ適用するようにし、同名の古い承認済みエントリを誤って再適用することがなくなった。複数のPENDING_HUMAN_REVIEWエントリが同時に存在する場合も、それらすべての内容を取り込むようにした(従来の「先頭の1件だけ」という暗黙の制約も合わせて解消した)。

\*\*検証\*\*: `tests/test_shield_rebuild.py`に1件追加し、同一`vulnerability_name`で2回提案・承認を行い、2回目に承認した内容が確実に`shield_rules.json`へ反映されることを固定した。本テストは修正前のコードに対して実際にFAILすること(`git stash`で一時的に旧実装へ戻して再現)を確認した上で、修正後にPASSすることを確認済み。`mini_pytest.py`再実行で`PASS=157`(§AS時点の156から新規1件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\### AU. tartarus/armageddon.py — 「Lucifer vs Sefer」の自己対戦が、実は防壁が一度も展開されない空の闘技場で行われていた (2026-10)

\*\*発見\*\*: `tartarus/armageddon.py`(攻撃生成AI「Lucifer」と防壁「Sefer」を戦わせ、突破された攻撃手法を学習して`raziel_ledger.json`の禁止イベントを拡充する自己対戦エンジン)の、Luciferが生成した攻撃ペイロードを実行するスクリプト生成部分を精査したところ、生成されるスクリプトが以下の2行のみで構成されていた:

```
from sefer import awaken
awaken()
# --- LUCIFER'S PAYLOAD ---
<payload_code がそのまま続く>
```

`sefer._michael_absolute_defense`(監査フック本体)は冒頭で`if not _is_guard_active(): return`を行う。`_is_guard_active()`は`sefer._active_stack`(`with Sanctum(...):`に入っている間だけ積まれるスタック)が空でないかを見ているが、`awaken()`は`sys.addaudithook()`でフックを\*\*登録\*\*するだけで、`_active_stack`には何も積まない。つまり`awaken()`を呼んだだけで一度も`with Sanctum(...):`に入らなければ、登録された監査フックは呼ばれるたびに即座に無条件でreturnするだけの、何も検査しない空のフックと等価だった。実機検証済み: この旧来の生成スクリプトと全く同じ構成(`awaken()`のみ、`with Sanctum(...):`無し)で`os.system('echo ...')`を実行したところ、一切遮断されずそのまま実行されることを確認した。

\*\*たとえ話\*\*: これは、ボクシングの「スパーリングで自分のガードの弱点を見つける」はずの練習なのに、実はコーチがミット(防具)を一度もつけずに、選手が打つパンチを全て素通しで受けていた、という状態である。選手(Lucifer)がどんな単純な(フェイントすら使わない)直球のパンチを打っても「打撃成立」と記録され続け、練習記録には「このジムの防御力は皆無だ」というデータが延々と積み重なるが、実際には防御側が一度も構えていなかっただけであり、本当のガードの弱点は何一つ見つかっていなかった。

\*\*原因\*\*: 本プロジェクトの規約として、`angels/raguel_template.py`が`src/openai_agent_loop.py`に対して既に検査している通り、「`sefer.Sanctum`は`awaken()`で登録するだけでなく、実際に`with Sanctum(...):`のコンテキスト内でファイルI/Oや実行を行わなければ、実防壁として機能しない」ことは本プロジェクト自身が既に把握している既知の規約だった。しかし`tartarus/armageddon.py`の生成スクリプトのテンプレート自体が、まさにこの規約に違反していた。検査する側(Armageddon自身)に、検査対象側(`openai_agent_loop.py`等)でなら既に発見・修正済みの欠陥が存在していた、という自己言及的な抜け漏れである。`armageddon.py`はMACアドレスゲート(`_verify_creators_air()`)により本番CI・このサンドボックスでは常に`sys.exit(666)`で起動不能なため、この欠陥はこれまで一度も実機のLucifer対戦では発覚していなかった。

\*\*対応\*\*: ペイロードを直接スクリプトに埋め込む方式ではなく、`tartarus/armageddon_core.py`に新設した`build_forge_script()`が、ペイロードを`repr()`で安全に文字列化し、`with Sanctum(allowed_dirs=[tartarus_dir], restrict_reads=True):`(`src/ollama_agent_loop.py`等の実運用コードと同一パターン)の中で`exec()`するスクリプトを生成するように変更した。ペイロードをインデント付きでそのまま埋め込む方式は、ペイロードが複数行の三重引用符文字列や空行を含む場合に生成スクリプトの構文自体が壊れるリスクがあったため、`repr()`文字列化 + `exec()`という、ペイロードの内容に関わらず安全に働く方式を採用した。

\*\*検証\*\*: `tests/test_armageddon_core.py`に3件追加した。(1) 実際に生成スクリプトをサブプロセスとして実行し、`os.system`を使った(難読化すら無い)単純な攻撃が確実に遮断されることを実機で確認する(これが本修正の核心)。(2) 正規の(禁止操作を使わない)ファイル書き込みは、`allowed_dirs`内であれば引き続き成功すること(過剰検知になっていないことの確認)。(3) ペイロードに引用符・バックスラッシュ・複数行の三重引用符文字列が含まれていても、生成スクリプトが構文的に壊れないこと。`mini_pytest.py`再実行で`PASS=160`(§AT時点の157から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\### AV. sefer/\_\_init\_\_.py — ネストした`Sanctum`の`allowed_dirs`絞り込みが、実際には\*\*広げる\*\*方向にも効いてしまい、サンドボックスをファイルシステム全体まで脱獄できた (2026-10)

\*\*発見\*\*: §AUで`tartarus/armageddon_core.build_forge_script()`を、AI生成ペイロードを`with Sanctum(allowed_dirs=[tartarus_dir], restrict_reads=True):`の内側で`exec()`する方式に修正した直後、「この新しい防御自体は本当に安全か」を再点検する目的で`Sanctum.__init__`のネスト処理(外側の`with Sanctum(...):`の中でさらに`with Sanctum(...):`を開いた場合の挙動)を精査した。すると、子スコープの`allowed_dirs`を親の範囲内に絞り込む判定が、以下の2条件をORで結合したものになっていた:

```
any(d == pd or d.is_relative_to(pd) for pd in parent_dirs)   # (A) dがpdの配下
any(pd == d or pd.is_relative_to(d) for pd in parent_dirs)   # (B) pdがdの配下(=dがpdの祖先)
```

(A)は「子のディレクトリが親のディレクトリの配下にある」という、意図通りの絞り込み判定である。しかし(B)は、子が親より\*\*広い\*\*、親の\*\*祖先\*\*ディレクトリを指定した場合にも真になってしまう。例えば親が`allowed_dirs=["jail_workspace"]`で、ネストした子が`allowed_dirs=["/"]`を指定すると、`"/"`はあらゆる絶対パスの祖先であるため(B)が真になり、子の実効的な`allowed_dirs`が`["/"]`(ファイルシステム全体)に\*\*昇格\*\*してしまう。

実機検証済み: `with Sanctum(allowed_dirs=["jail_workspace"]):`の内側で`with Sanctum(allowed_dirs=["/"]):`を開き、`/tmp/`配下への書き込みを試みたところ、実際に書き込みが成功した(例外が発生せず、マーカーファイルが作成された)。これは`_get_current_policy()`が返す辞書の中身だけがおかしいという静的な欠陥ではなく、\*\*実際にサンドボックス外への書き込みが成功する\*\*、本物のサンドボックス脱獄であることを確認した。

\*\*たとえ話\*\*: これは、ビルの入館証システムで「エリア管理者が、自分の管理エリア(例:3階の会議室だけ)を部下に一時的に割り当てる際、部下はその範囲を\*\*狭める\*\*ことしかできない」という設計のはずが、実装を見ると、部下が「私はビル全体(1階〜地下まで)を管理したい」と自己申告しただけで、その自己申告された\*\*より広い\*\*範囲がそのまま有効な権限として認められてしまう、という状態である。部下(ネストした`Sanctum`)が「親より広い範囲」を名乗った瞬間、入館証システムはそれを「親の管理エリアの外側」としてではなく「親の管理エリアを包含するもの」として誤って解釈し、結果的に部下に建物全体への入館権限を与えてしまっていた。

\*\*原因\*\*: ネストした`Sanctum`の絞り込みロジックを実装した際、「子は親の配下でなければならない(子 ⊆ 親)」という設計意図を、パス包含関係の\*\*両方向\*\*(「子が親の配下にあるか」と「親が子の配下にあるか」)でチェックしてしまい、本来チェックすべきでない後者の方向(親が子の配下にある、つまり子が親の祖先である)まで「絞り込みとして許可」の条件に含めてしまっていた。`allowed_hosts`側の絞り込みは単純な集合の`.intersection()`で実装されており、この種の方向性の誤りが入り込む余地がそもそも無かった(本修正の過程で確認済み、該当箇所は変更していない)。本件はこのネスト処理自体を直接テストする既存の回帰テストが一件も存在しなかったため、`Sanctum`の基本的な単方向の防御(`allowed_dirs`外への書き込みを拒否する)を検証する既存テスト群だけでは、ネストした場合の絞り込みの崩壊には一度も気付けなかった。

本件の発見経緯そのものが重要である。§AUの修正は「AI生成コードを`with Sanctum(...):`の中で`exec()`する」という、本プロジェクトの実運用コード(`src/ollama_agent_loop.py`等)と同一の、正しいパターンへの修正だった。しかし`sefer.inquisition()`の`forbidden_modules`(`{"pickle", "ctypes", "importlib", "socket", "urllib", "requests", "http", "subprocess", "os"}`)と`anjo_interceptor/intent_checker.py`の`IntentInterceptor.forbidden_modules`(`{"os", "subprocess", "sys", "pty"}`)のいずれにも`"sefer"`自体は含まれていないことを確認した。つまりAI生成コードは`import sefer`し、`sefer.Sanctum(allowed_dirs=["/"])`を自ら開くことを一切禁止されていない。もし本脆弱性を直さずに§AUの修正だけを入れていた場合、「`with Sanctum(...):`の中で実行する」という正しい防御パターンそのものが、十分に賢い(あるいは単に`sefer`を知っている)攻撃コードによって、ネストした`Sanctum`を自分で開くだけで完全に無力化されてしまう、という事態になっていた。§AUの修正によって生まれた新しい信頼の土台(「`Sanctum`の中で実行すれば安全」)を、本件の修正前の状態のまま使っていたら、その土台自体に穴が開いていたことになる。

\*\*対応\*\*: 絞り込み条件から(B)(「親が子の配下にある」方向の判定)を削除し、(A)(「子が親の配下にある」方向の判定)のみを残した。これにより、子が親より広い(または無関係な)ディレクトリを指定した場合、そのディレクトリは絞り込み結果から単純に除外される(昇格は起こらない)。子が親の真の配下にある、正当な狭いディレクトリを指定した場合の挙動(絞り込みが機能し、その狭い範囲内でのみ操作が許可される)は変更していない。

\*\*検証\*\*: `tests/test_sanctum_nested_allowed_dirs_widening.py`を新設し、5件追加した。(1) 親が狭い`allowed_dirs`を持つ状態で子が`"/"`を指定しても、`_get_current_policy()`が返す実効的な`allowed_dirs`に`"/"`が含まれないこと。(2) (1)の計算結果だけでなく、実際に親の許可範囲外への書き込みを試みて`LossOfAtaraxia`が発生し、ファイルが作成されないことを実機で確認する(これが本修正の核心)。(3) 子が親の真の配下にある狭いディレクトリを指定した場合、その狭い範囲内への書き込みは引き続き成功すること(過剰検知になっていないことの確認)。(4) 親の許可範囲内ではあるが子の狭い範囲外への書き込みは、引き続き`LossOfAtaraxia`で遮断されること(絞り込み自体が無効化されていないことの確認)。(5) `allowed_hosts`側のネスト絞り込みが`.intersection()`により引き続き正しく機能し、子が親に無いホストを追加指定しても実効的な許可ホスト集合が広がらないことを、対称性の確認として固定した。`mini_pytest.py`再実行で`PASS=165`(§AU時点の160から新規5件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*残存する限界・関連する未調査事項(誠実に明記する)\*\*: 本修正は`sefer.Sanctum`のネスト処理そのものの欠陥を直すものであり、「AI生成コードが`import sefer`して`Sanctum`を自分で開く」という攻撃経路自体を塞ぐものではない(むしろ、その経路が開かれていても安全であるようにするための修正である)。`forbidden_modules`系のブロックリストに`"sefer"`自体を加えることも対策として考えられるが、これは`sefer`を正当な理由で`import`する必要がある既存の正規コード(本プロジェクト自身の多くのモジュールを含む)を区別する必要があり、本件の範囲を超える別の設計判断を要するため、今回は着手していない。\*\*追記(2026-10 再調査により確定)\*\*: 「本番の`src/ollama_agent_loop.py`・`src/openai_agent_loop.py`がAI生成コードを`exec()`しているか」を未確認のまま残していた点を、本件のすぐ後に実際に両ファイルの`_execute_safe_action`を読み直して確認した。両者とも、AIからは`action`("read"/"write"/"list")と`target`(パス文字列)のみを受け取り、`target.read_text()`/`target.write_text()`/`mkdir()`といった定型操作のみを行う。`exec()`/`eval()`でAI生成コードを実行する経路は存在せず、`with Sanctum(allowed_dirs=[str(self.workspace_root)], ...)`の`allowed_dirs`もAI入力ではなく`self.workspace_root`固定(呼び出し元のコードに静的に書かれた値)である。したがって本件(§AV)のネスト脱獄は、この2つの本番エージェントループからは現時点では到達できないことを確定した。これは「今後もAIが`Sanctum`のallowed_dirsを自ら指定できる経路が追加されない」ことまでは保証しない――本件の修正自体(ネストしても広げられない)がその種の将来の変更に対する構造的な防御線であることに変わりはない。

\### AW. src/metatron\_orchestrator.py — `CassielsVeil`の通信遮断結界が、天使自身の正規のOllama学習通信まで毎サイクル確実にブロックしていた (2026-10)

\*\*発見\*\*: §AVの修正後、本セッションの既存の知見(GRIMOIRE.md §L: 「`cassiels_veil.CassielsVeil`は統合しない(デモとして保持)」——理由は、本クラスの`socket.socket`を丸ごと置き換える通信遮断が、実運用ループが依存するローカルOllamaサーバーへの通信まで一緒に遮断してしまうため)を思い出し、「この決定が本当に全ファイルで守られているか」を横断的に確認する目的で`src/metatron_orchestrator.py`(§Lの対象だった旧ファイル群より\*後から\*新設された、各天使クラスを統括する正式なオーケストレータ)を精査した。すると、`execute_holy_war()`が`self.cassiel.activate_seal()`(`CassielsVeil`の結界展開)を、`self.angel.defend_and_execute(payload, ...)`の直前で呼んでいた。この`defend_and_execute()`は内部で`learn_threat()`を呼び、これは防御側AI(Blue Team)に未知の攻撃パターンを分析させるため、実運用のローカルOllamaサーバーへ`ollama.chat(...)`で通信する。つまり、§Lで既に判明していた「通信遮断がOllama通信まで一緒に遮断する」という問題が、§Lの対象ファイル群とは独立に新設された本ファイルで、まさに禁止されていたはずの統合がそのまま行われてしまっていた。

実機検証済み: `CassielsVeil.activate_seal()`展開中に`socket.create_connection(('127.0.0.1', 11434), ...)`(ローカルOllamaサーバーへの接続と同種の経路)を試みたところ、`ConnectionRefusedError`で確実に遮断されることを確認した。また、スタブ化した`ollama.chat`が呼ばれた瞬間の`socket.socket`の状態を記録するテストを書いたところ、`craft_poison()`(結界展開\*前\*のOllama呼び出し)は`True`(遮断されていない)、`learn_threat()`(結界展開\*後\*のOllama呼び出し)は`False`(遮断されている)という結果になり、まさに疑っていた通りの非対称なブロックが実際に発生することを確認した。

\*\*たとえ話\*\*: これは、ボディーガード(カシエルの結界)が「不審な電話を一切取り次がせない」という方針で雇われたのに、実際に配置された場所が、依頼主(天使自身)が部下(Ollama)に電話で指示を出す、その電話線の途中だった、という状態である。ボディーガードは言われた通りの仕事(電話線を物理的に遮断する)を正確に実行しているのに、配置が間違っていたため、外部からの不審な電話だけでなく、依頼主自身の業務連絡まで毎回確実に切られてしまう。結果として、依頼主が部下に「この新しい手口を学んでおけ」と指示を出そうとする(`learn_threat`)たびに、その指示自体が通らず、部下は何も学習できないまま、何も知らなかった時と同じ状態で次の攻撃に対処し続けることになる。

\*\*原因\*\*: §Lの決定(「`CassielsVeil`はローカルOllama通信を壊すため実運用パイプラインに統合しない」)は、当時存在していた個別ファイル群(`mythos_weaponization.py`等、既に`aegis_system.py`の新設に伴い統合・整理された旧ファイル群)を対象に下されたものだった。その後`src/metatron_orchestrator.py`が、既存の`RazielIntelligence`・`SamaelWeaponization`(`intelligence_cycle.py`)・`EvolvingAngel`(`angelic_evolution.py`)を束ねる新しい統括クラスとして新設された際、「もっと多層的な防御に見せるため」`CassielsVeil`を追加で組み込む判断がなされたと見られるが、その時点で§Lの決定(なぜ統合しないことにしたか)が再確認されなかった。`EvolvingAngel.defend_and_execute()`が内部でOllama通信を行うという事実は、`angelic_evolution.py`を読まなければ分からず、`metatron_orchestrator.py`だけを見ていると「`CassielsVeil`の結界を追加するのは安全そうだ」と見えてしまう、モジュール間の依存を見落としやすい構造的な死角だった。

\*\*対応\*\*: `src/metatron_orchestrator.py`から`CassielsVeil`のimport・インスタンス化・`activate_seal()`/`deactivate_seal()`の呼び出しを削除した。AI生成ペイロードの実行時の通信遮断そのものは、`defend_and_execute()`が呼ぶ`AegisSystem.execute_ai_intent()`内で、既にDockerコンテナの`--network none`によってOSレベルで提供されている(`src/sandalphon_jail.py`、§Aで導入)。`CassielsVeil`の結界はそれより弱い追加の一層でしかなく、ここでの展開は保護の上積みなしに正規の学習通信を壊すだけだったため、削除という判断をした。レポート生成文言(`GabrielRevelation.generate_report`)の「カシエルの結界(通信遮断)」という記述も、実際に機能している防御層(認知的防壁・Dockerの隔離結界)に即した記述へ修正した。

\*\*検証\*\*: `tests/test_metatron_orchestrator_cassiel_ollama.py`を新設し、2件追加した。(1) `execute_holy_war()`の実行中、`ollama.chat`が呼ばれた瞬間ごとに`socket.socket`が本物のクラスのままであること(=正規の学習通信が自分自身の結界で遮断されていないこと)を固定する(これが本修正の核心)。本テストは修正前のコードに対して実際に`[True, False]`(2回目の呼び出しがブロックされている)でFAILすることを確認した上で、修正後は`[True, True]`でPASSすることを確認済み。(2) サイクル終了後に`socket.socket`が元のクラスへ確実に復元されていること(他のテストへの汚染防止)。`mini_pytest.py`再実行で`PASS=167`(§AV時点の165から新規2件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*自己点検\*\*: 本件は私自身が過去に修正した箇所の不備ではなく、`metatron_orchestrator.py`新設時に元から存在していたバグである。しかし発見経緯そのものは、既に確定していたはずの設計判断(§L)が、後から追加されたコードで横展開を忘れられ、再び同じ種類の問題として表出した、という本セッションで繰り返し見ている「教訓が一箇所にしか適用されない」パターンの一例であり、正直に次の調査対象として残していた「§AVの関連する未調査事項」の確認作業中に見つけたものである。

\### AX. tools/auto\_red\_team.py — 二重防壁を一度も試さずに「48件全て突破」という完全に偽の致命的敗北を報告していた (2026-10)

\*\*発見\*\*: 本ツール(難読化した攻撃ペイロードを自動生成し、ガブリエル(静的AST解析)・ミカエル(動的audit hook)の二重防壁に本当に撃ち込んで検証する、既存のレッドチーム用スクリプト)を精査したところ、実行すると必ず「Successful Bypasses: 48(全件突破)」という、致命的な結果を報告することに気づいた。実機で直接実行し(`echo hacked`が48回標準出力に現れることも確認)、以下2つの独立したバグが原因であることを確認した:

  1. 第一防壁の判定部分で、`inquisition(payload)`(ガブリエルの静的解析)の戻り値を一度も確認せず、ただ呼ぶだけで次の行に進んでいた。`inquisition()`は違反を検知しても例外を送出せず、Findingのリストを返すだけの純粋関数である(実運用の呼び出し側である`src/aegis_system.py`の`execute_ai_intent()`は、戻り値から`severity == "critical"`なFindingを自分で判定して`PermissionError`を送出している)。そのため直後に書かれていた`except PermissionError:`は、そもそも`inquisition()`が一度もそのような例外を送出しないため、\*\*一度も発火し得ない死んだコード\*\*であり、Gabrielの判定結果は呼ばれているだけで完全に無視されていた。
  2. 第二防壁の判定部分で、`exec(payload, {})`が`with Sanctum(...):`の\*外\*で直接呼ばれていた。本ファイル冒頭の`awaken()`はOSレベルの監査フック自体を\*登録\*するだけであり、§AU(`tartarus/armageddon.py`)で発見したのと全く同じ理由(`_active_stack`が空のままでは登録されたフックは何も検査せず即座にreturnする)で、実質的に無効化されていた。さらに、Sanctumが実際に遮断する際に送出する例外は`sefer.LossOfAtaraxia`(`BaseException`を直接継承し、`Exception`経由ではない特殊な設計)であるが、修正前のコードは`except RuntimeError as e: if "Michael's Sword" in str(e):`という、\*\*型も文言も一致しない\*\*捕捉を書いていた。たとえSanctumを正しく経由していても、この捕捉句は本物の遮断を一度も捉えられなかった。

\*\*たとえ話\*\*: これは、新しい金庫(防壁)の強度試験を依頼された検査員が、実際には金庫の鍵を一度も掛けず(第一の欠陥:検査結果を読まない)、さらに金庫のドア自体を壁に取り付けず床に置いたまま(第二の欠陥:ドアが機能する文脈の外で試験している)、その状態でハンマーを48回打ち込んで「全48回、ハンマーが金庫を貫通しました。この金庫は完全に壊れています」という報告書を提出していた、という状態である。金庫(本物のGabriel/Sanctum)は実際には何一つ試されておらず、検査員が検査の手順そのものを間違えていたために、存在しない欠陥が「致命的」として報告されていた。

\*\*原因\*\*: このファイルは`inquisition()`・`sefer`のAPIが「違反時に例外を送出する」という誤った前提で書かれていたと見られる。実際の`inquisition()`は一貫して「検知結果のリストを返すだけで、判断・強制は呼び出し側に委ねる」設計であり(`src/aegis_system.py`の正しい使用例と比較すれば一目で分かる非対称だった)、また`sefer`の例外階層(`LossOfAtaraxia`が`BaseException`直接継承である特殊な設計)も本ファイルでは踏まえられていなかった。本ツールはCIのどのワークフローからも呼ばれておらず(`grep`で確認済み)、テストも一度も存在しなかったため、この「常に全滅」という明らかにおかしい結果が長期間放置されていたと考えられる。

\*\*対応\*\*: (1) `inquisition(payload)`の戻り値を`src/aegis_system.py`と同じパターンで`severity == "critical"`なFindingの有無として判定し、検知された場合は`blocked_by_gabriel`を加算して次のペイロードへ進むようにした。(2) `exec(payload, {})`を`with Sanctum(allowed_dirs=[], allowed_hosts=[]):`の中に移動し、Michaelの監査フックが実際に有効な状態で実行されるようにした。(3) 捕捉する例外を`except LossOfAtaraxia:`(`sefer`から新たにimport)に変更した。

\*\*検証\*\*: `tests/test_auto_red_team_harness.py`を新設し、2件追加した。(1) 修正後のツールを実際にサブプロセスとして実行し、本物のGabriel/Sanctumに対して48件の難読化ペイロードが実行まで到達しない(`Successful Bypasses: 0`)ことを実機で確認する(これが本修正の核心)。(2) 全48件が実際にGabrielの裸名チェック(`getattr`/`__import__`/`exec`というリテラルな識別子は、文字列引数の難読化レベルに関わらずAST上に現れるため検知される)で検知され、`Blocked by Gabriel: 48`として正しく集計されることを確認する。両テストとも、修正前のコードに対しては実際にFAILすること(`git stash`で一時的に旧実装へ戻して再現、`echo hacked`が実際に標準出力に現れることも確認)を確認した上で、修正後にPASSすることを確認済み。`mini_pytest.py`再実行で`PASS=169`(§AW時点の167から新規2件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*残存する限界(誠実に明記する)\*\*: 修正後、本ツールの48件の攻撃ペイロードは全てGabrielの段階で検知され、Michaelの動的フック層は一度も実際には試されていない(`Blocked by Michael`は常に0のままである)。これは、本ツールが用意している「4段階の難読化」が、実際には`os`/`system`という\*文字列引数\*だけを難読化しており、`getattr`/`__import__`/`exec`という\*呼び出し関数自体のリテラルな識別子\*は一度も隠していないためである。つまり本ツールは、Gabrielの「裸名チェック」を回避するレベルの難読化(例: `sys.modules['os'].system(...)`のようにgetattr/importlibを経由しない間接呼び出し)を一つも含んでいない。これは本修正の範囲外の、ツールの試験範囲そのものに関する別の限界として正直に記録しておく。

\### AY. `sefer.inquisition()`(Gabriel)に`sys.modules['os'].system(...)`型の静的解析バイパスを発見、ただしMichael(動的フック)が正しく補っていることを確認 (2026-10)

\*\*発見\*\*: §AXで`tools/auto_red_team.py`を修正した際、「このツールの難読化は文字列引数だけを難読化しており、呼び出し関数自体(`getattr`/`__import__`/`exec`)のリテラルな識別子は一度も隠していない」という限界を正直に記録した。この限界を踏まえ、「では、呼び出し関数自体の識別子を隠す、本当の静的解析バイパスは存在するか」を実際に試した。`sys.modules['os'].system('echo ...')`(`getattr`・`__import__`・`importlib`のいずれも使わず、`sys.modules`という辞書(Subscript)経由でモジュールオブジェクトを直接取得する手法)を`sefer.inquisition()`に通したところ、Findingが一件も返らないことを実機で確認した。

原因は3点の複合: (1) `inquisition()`の`_qualified_call_name()`は`ast.Attribute`/`ast.Name`の連鎖しか辿らず、`sys.modules['os']`の部分が`ast.Subscript`であるため、そこで再帰が止まり完全修飾名(`"os.system"`)を復元できない。(2) 呼び出し式の末端の属性名は`"system"`のみであり、`forbidden_funcs`に含まれるのはドット付きの`"os.system"`であって裸の`"system"`ではないため一致しない。(3) `"sys"`自体は`forbidden_modules`(`pickle`/`ctypes`/`importlib`/`socket`/`urllib`/`requests`/`http`/`subprocess`/`os`)に含まれていないため、`import sys`の行も無害と判定される。

\*\*たとえ話\*\*: これは、受付の警備員が「"刃物"という単語が書かれた持ち込み申請書は止める」というルールで運用されているところに、申請書に「刃物」とは一言も書かず、代わりに「備品棚の3番目の引き出しの中にあるもの」という、間接的な指し方で同じ刃物を指定した場合である。警備員(Gabrielの単語マッチング)はルール通りに申請書を読んで「刃物という単語はない、問題なし」と判定してしまうが、実際に持ち込まれる物自体は変わっていない。

\*\*重要な確認(多層防御が機能していることの実証)\*\*: このバイパスが実際に悪用可能かを確かめるため、同じペイロードを`awaken()`後に`with Sanctum(allowed_dirs=[], allowed_hosts=[]):`の中で実際に`exec()`した。結果、`sefer.LossOfAtaraxia: [Sefer] Tripwire: Hard-denied event 'os.system' blocked.`で確実に遮断されることを確認した。これは、Michael(`sefer._michael_absolute_defense`、`sys.addaudithook()`によるOSレベルの監査フック)が、Pythonコードがどのような属性アクセス経路で`os.system`に到達したか(直接呼び出しか、`sys.modules`経由の間接呼び出しか)に関わらず、実行時に発火する`os.system`というaudit event自体をCレベルで捕捉しているためである。つまり本番でAI生成コードを実際に実行する唯一の経路(`src/aegis_system.py`の`execute_ai_intent()`、および各`*_agent_loop.py`)は、Gabrielの静的解析だけに頼っておらず、実行時に必ずMichaelの層を通るため、本バイパスは実害に至らない。`src/ast_scanner.py`のKNOWN_LIMITATIONSが既に一般論として述べていた「denylist方式の静的解析には構造的な限界があり、OSレベルの隔離を一次防衛線とすべき」という設計方針が、教材モジュールだけでなく実運用の`sefer.inquisition()`自身にも、まさにこの通りに当てはまり、かつ正しく機能している実例であることを実機で確認できた。

\*\*対応\*\*: コードの修正は行っていない(Gabriel単体の静的解析を強化して`ast.Subscript`経由のパターンを個別に潰すことも検討したが、denylist方式は本質的にこの種のいたちごっこになりやすく、実際の防御はMichaelのOSレベル層が担っているため、優先度は低いと判断した)。代わりに、`tests/test_gabriel_subscript_bypass_michael_backstop.py`を新設し、(1) Gabrielがこのバイパスを検知しない(既知の限界)こと、(2) それでもMichaelが実行時に確実に遮断すること、の両方を実機テストとして固定した。これにより、今後誰かが「Gabrielの静的解析だけで十分」という誤った前提でMichaelの層を弱める変更をした場合に、このテストが検知できるようにした。

\*\*残存するリスク(誠実に明記する)\*\*: `angels/sariel_fallen_auditor.py`(CI上で`adapters/`配下のスクリプトをGabrielの静的解析のみで検査し、動的実行は一切行わない)は、本バイパスに対して無力である。ただし`adapters/`は外部AIが生成する未検証コードではなく、保守者自身が書く内部ツール(証明書発行・データ変換等)であるため、このCI検査の目的は「悪意ある攻撃者からの防御」ではなく「保守者の不注意による危険コードの混入検知」であり、実害の想定は低いと判断し、本件の範囲では`sariel_fallen_auditor.py`自体の修正は行わなかった。

\*\*検証\*\*: `mini_pytest.py`再実行で`PASS=171`(§AX時点の169から新規2件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\### AZ. `angels/firmament_enclave_tee.py` — 無関係な`os.getenv`呼び出しが1つでもあれば、ファイル内の本物のハードコード漏洩が隠れてしまっていた (2026-10)

\*\*発見\*\*: 本スクリプト(実TEE未接続のため代替として、センシティブな環境変数名が「安全な読み取り文脈」を伴わずハードコードされていないかを検査するCI必須ステップ)を精査したところ、判定条件`f'"{key}"' in text and "os.getenv" not in text and "os.environ" not in text`の`not in text`が、\*\*ファイル全体\*\*を対象に判定されていることに気づいた。これは、同一ファイル内のどこか別の場所(全く無関係な設定値の取得等)で一度でも`os.getenv`/`os.environ`が使われていれば、ファイル内の\*別の行\*にある、センシティブなキー名と実際の秘密値がハードコードされた本物の漏洩パターン(例: `{"OPENAI_API_KEY": "sk-実際の値"}`)まで、一括で検査対象外にしてしまう構造的な欠陥だった。

実機検証済み: `import os`と無関係な`os.getenv("SOME_UNRELATED_VAR")`を含む一時ファイルの別の行に`DEFAULT_CONFIG = {"OPENAI_API_KEY": "sk-THIS_IS_A_REAL_LEAKED_SECRET_VALUE..."}`という本物の漏洩パターンを混在させたところ、修正前の判定ロジックはこれを一件も検知しなかった。

\*\*たとえ話\*\*: これは、空港の保安検査で「パスポート番号が書かれた紙を、正規の申告書以外の場所で持っていないか」を確認する係員が、「申告書一式(カバン一つ分の全ての紙)の中にどこかに1枚でも正規の申告書が混じっていれば、カバン全体を"検査済み・問題なし"とする」という運用をしていた、という状態である。本物の密輸品(ハードコードされた秘密)が、無関係な正規の書類と\*同じカバン(ファイル)\*に入っているだけで、密輸品自体は一度も開いて確認されないまま通過してしまう。

\*\*原因\*\*: この判定は元々「このファイルは`os.getenv`/`os.environ`を使って安全に環境変数を読み取っている文脈かどうか」を大まかに推定する簡易ヒューリスティックとして書かれたと見られるが、「ファイル単位」という粒度が粗すぎた。1ファイルが複数の環境変数・複数の役割を持つ関数を含むのは一般的であり、「ファイル内のどこかで1回でも安全な読み取りパターンが使われていれば、ファイル全体を信頼する」という前提は、同じファイル内に無関係な正規コードと本物の漏洩が共存するケースを想定していなかった。

\*\*対応\*\*: 判定をファイル単位から\*行単位\*に変更した。「そのキー名を含む行自体に`os.getenv`/`os.environ`が無い」場合にのみ疑わしいと判定するようにした(`os.getenv("OPENAI_API_KEY")`のように、キー名と安全な読み取り呼び出しが同じ行にある正規のパターンは引き続き誤検知しない)。この変更に伴い、本スクリプト自身が`SENSITIVE_ENV_KEYS`という denylist 自体を定義・報告するためにキー名を文字列として含む(漏洩ではない)ことが新たに自己検知の原因となったため、スキャン対象から自身のファイルパスを明示的に除外する処理を追加した。また、テスト容易性のため、スキャン本体を`scan_for_hardcoded_sensitive_env_keys(root, self_path)`という独立関数に切り出した(`angels/_common.py`の`scan_for_leaked_secrets(root)`と同じ、テスト用に`root`を注入可能にする既存パターンに合わせた)。

\*\*検証\*\*: `tests/test_firmament_enclave_tee.py`を新設し、3件追加した。(1) 同一ファイル内に無関係な`os.getenv`呼び出しがあっても、別の行にあるハードコードされた秘密が確実に検知されること(これが本修正の核心)。(2) `os.getenv("OPENAI_API_KEY")`のような、キー名と安全な読み取りが同じ行にある正規のパターンを誤検知しないこと(過剰検知になっていないことの確認)。(3) スクリプト自身のソースファイル(denylist定義そのもの)を誤検知しないこと。修正後、本スクリプトを実際にリポジトリ全体に対して実行し、PASSすることを確認した(自己検知の除外が正しく機能していることの実機確認)。`mini_pytest.py`再実行で`PASS=174`(§AY時点の171から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\### BA. `angels/ophanim_thousand_eyes.py` — 「外部スクリプト検知」が`https?://`形式しか見ておらず、プロトコル相対URL(`//`)の読み込みを素通りさせていた (2026-10)

\*\*発見\*\*: `architecture.html`に外部スクリプト読み込み(サプライチェーンリスク)が紛れ込んでいないかを検査するCI必須ステップを精査したところ、検知用の正規表現`<script[^>]+src=["\']https?://[^"\']+["\']`が、`src`属性の値が`http://`または`https://`で明示的に始まる場合しか一致しないことに気づいた。HTMLには`src="//evil-cdn.example.com/malicious.js"`のような\*プロトコル相対URL(scheme-relative URL)\*という正当な記法があり、ブラウザはスキーム部分を省略しているだけで、実行時のページのプロトコル(http/httpsのいずれか)をそのまま使って\*必ず外部ホストから\*スクリプトを取得する。つまりこれも定義上「外部スクリプト読み込み」そのものでありながら、`https?://`という文字列を含まないため、検知を完全に素通りする。

実機検証済み: `<script src="//evil-cdn.example.com/malicious.js"></script>`を含むHTML断片に対し、修正前の正規表現は一件もマッチしなかった(`hits=[]`)。

\*\*たとえ話\*\*: これは、空港の手荷物検査で「爆発物の受け取りサインとして"EXPLOSIVE"という英単語がラベルに書かれていないか」だけを確認する係員が、同じ荷物にフランス語で"EXPLOSIF"と書かれていれば、意味は全く同じ危険物であるにもかかわらず素通りさせてしまう、という状態に近い。プロトコル相対URLは「外部から読み込む」という意味では`https://`形式と完全に同じ効果を持つのに、表記の綴りが違うだけで検査対象から漏れていた。

\*\*原因\*\*: この検知ロジックはおそらく「外部スクリプト = URLがhttp(s)で始まる」という最も典型的なパターンだけを想定して書かれ、HTML/URL仕様上もう一つの正当な「外部参照」の書き方であるプロトコル相対URLを見落としていた。かつ、プロトコル相対URLは`https?://`という文字列を意図的・偶然的に含まないため、本検査が防ぐと主張しているまさにその種の単純な文字列照合回避の一種にもなっていた。

\*\*対応\*\*: 検知用の正規表現を、`(?:https?:)?//`(スキームは省略可能、ただし`//`は必須)に拡張し、`https?://`形式とプロトコル相対`//`形式の両方を外部スクリプトとして検知するようにした。ローカルの相対パス(`./app.js`や`app.js`)はいずれも`//`を含まないため誤検知しない。テスト容易性のため、検知ロジックを`find_external_scripts(text)`という独立関数に切り出した(`angels/firmament_enclave_tee.py`の§AZ修正と同じ、ロジックを関数化してテストから直接検証可能にする既存パターンに合わせた)。

\*\*検証\*\*: `tests/test_ophanim_thousand_eyes.py`を新設し、3件追加した。(1) プロトコル相対URLの外部スクリプトが検知されること(これが本修正の核心、修正前のコードに対してこのテストが失敗することを`git stash`で確認済み)。(2) 元々検知できていた`https://`形式が引き続き検知されること(回帰防止)。(3) ローカルの相対パス(`./app.js`・`app.js`)を誤って外部スクリプトと判定しないこと(過剰検知になっていないことの確認)。修正後、本スクリプトを実際の`architecture.html`(現状`<script>`タグを含まない)に対して実行し、PASSすることを確認した。`mini_pytest.py`再実行で`PASS=177`(§AZ時点の174から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*残存する限界\*\*: 本修正は`<script src="...">`属性の外部URL検知範囲を広げたものであり、インラインスクリプト(`<script>...fetch('https://evil.com')...</script>`)内のネットワークアクセスや、`<link rel="stylesheet" href="...">`等の他のタグによる外部リソース読み込みは、本検査の対象外のまま(元々のスコープ外であり、今回のスコープ拡張でも手を付けていない)。これらは別の脆弱性として将来の調査対象になり得るが、本件の修正対象(「外部\*スクリプト\*読み込み」という既存スコープ内での検知漏れ)とは区別して正直に記録する。

\### BB. `src/adversarial_evolution.py` — `AegisSystem.execute_ai_intent()`の事前検閲を通過しただけで「防壁を突破した」と断定し、実際にSanctum(Michael)で実行して確かめていなかった (2026-10)

\*\*発見\*\*: 「怪物(レッドチームAI)」に攻撃ペイロードを生成させ、Pleromaの防壁に激突させる自己対戦シミュレーションを精査したところ、`self.aegis.execute_ai_intent(content, target)`が例外を投げずに戻った時点で、無条件に`print("第N世代の攻撃が防壁を突破しました。（あり得ない事態です）")`としてループを終了していることに気づいた。しかし`execute_ai_intent()`自身のdocstring(`src/aegis_system.py`)には「実際のファイルI/O・コード実行は、呼び出し側が`sefer.Sanctum`の中で行う必要がある。AegisSystemはSanctumの代替ではなく、Sanctumの前段に立つ追加の防御層である」と明記されている。つまり`execute_ai_intent()`はGabriel(静的AST解析)・IntentInterceptor(ハニーポット・トラバーサル検知)・Dockerの隔離結界内での使い捨てドライランという\*事前検閲\*のみを行い、実際にコードを実行してOSレベルの監査フックに通すかどうかは、呼び出し側の責務として明示的に残されている。本スクリプトはこの責務を一度も果たしていなかった。

実機検証済み: 攻撃生成プロンプトが明示的に指示している「"os"や"eval"のような文字列を直接使わずにOSコマンドを実行する」という回避手法の一例として、`open("パス", "w").write("pwned")`という、importも禁止関数名(`forbidden_funcs`/`forbidden_calls`)も一切使わないペイロードを試したところ、Gabrielの`inquisition()`は`findings=[]`(無傷で通過)、IntentInterceptorの`evaluate_action()`も例外を投げずに通過することを確認した。一方、同じペイロードを実際に`awaken()` + `with Sanctum(allowed_dirs=[], allowed_hosts=[]):`の中で`exec()`すると、Michael(SanctumのOS監査フック)が`LossOfAtaraxia: Unauthorized write access to '...'`で確実に遮断することも確認した。つまり修正前のロジックでは、このペイロードに対して`execute_ai_intent()`は`True`を返し、本スクリプトは「あり得ない事態」という\*偽の全面突破\*を報告してしまう状態だった。

\*\*たとえ話\*\*: これは、ボディガードチーム(Aegis)が「怪しい単語を言っていないか」「金属探知機に引っかからないか」「監視カメラの前での予行演習で問題を起こさないか」という\*事前の身辺調査\*だけを済ませて「異常なし」と報告し、本人(Michael、本物の警備ゲート)の前を一度も実際に通さずに「侵入者は要人警護を突破した」と結論づけてしまうようなものである。事前調査を通過したことと、本物の警備ゲートを実際に通過したことは全く別の事実だが、本スクリプトはこの2つを混同していた。

\*\*原因\*\*: この種の自己対戦シミュレーションの正しい形は、`tartarus/armageddon.py`(§AUで修正済み)が示している通り、「静的・事前検閲を通過したコードを、実際にSanctum/Michaelの中で実行し、本当に目的の副作用(ファイル作成・コマンド実行等)が成立するかどうか」で勝敗を判定することである。本スクリプトはそれを行わず、`execute_ai_intent()`という\*前段の検閲層\*の結果だけで最終判定を下していた。これは本セッションで既に2件発見・修正した同種のバグ(§AU: `tartarus/armageddon.py`が`awaken()`のみでSanctumコンテキストに入らず実行していた、§AX: `tools/auto_red_team.py`がMichaelの遮断を一度も実際に試さず「48件全て突破」と誤報告していた)と同じ系統の、3件目の「検閲通過と実行結果を混同する」欠陥だった。

\*\*対応\*\*: `src/adversarial_evolution.py`に`execute_payload_under_sanctum(content)`という新しい関数を追加した。`execute_ai_intent()`が例外を投げずに通過した後、必ずこの関数を呼び、`awaken()` + `with Sanctum(allowed_dirs=[], allowed_hosts=[]):`の中で実際に`content`を`exec()`する(攻撃者生成コードにファイル書き込み・外部接続いずれの正当な権限も無いため、`allowed_dirs`/`allowed_hosts`は両方空とし、最も厳格な検証を行う)。`LossOfAtaraxia`が発生した場合は`RuntimeError`に包んで既存の`except Exception`分岐に流し、既存の「防壁迎撃→フィードバックして次世代へ」というループ構造と一貫させた。これにより、「突破」の判定が、事前検閲(Gabriel/IntentInterceptor/Dockerドライラン)に加えて、実際のSanctum/Michaelでの実行結果にも依存するようになった。

\*\*検証\*\*: `tests/test_adversarial_evolution_sanctum_execution.py`を新設し、4件追加した。(1)・(2) 前提確認として、`open().write()`バイパスがGabriel・IntentInterceptorの双方を無傷で通過することを固定。(3) 修正の核心として、同じペイロードを`execute_payload_under_sanctum()`に通すと`LossOfAtaraxia`が発生し、実際にファイルが作成されないことを確認(`git stash`で旧コードに対して`ImportError`で失敗することも確認済み)。(4) 回帰防止として、ファイルI/O・外部接続を一切行わない本当に無害なコード(`x = 1 + 1`)は正常に完了すること(過剰検知になっていないこと)を確認した。`mini_pytest.py`再実行で`PASS=181`(§BA時点の177から新規4件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*残存する限界\*\*: 本修正は`AegisSystem.execute_ai_intent()`単体のバイパス(Gabriel/IntentInterceptorの検知漏れ)を補うものではなく、既に§AYで確認済みの通り、Gabriel/IntentInterceptor単体の静的解析には引き続き限界が残る。本修正が固定するのは「その限界があっても、本スクリプトの最終判定が実際のMichaelの実行結果を経るようになった」という、このシミュレーション自身の報告の正確性のみである。

\### BC. `angels/metatron_scripture_seal.py`・`raguel_template.py`・`sandalphon_decree.py`・`zadkiel_shield_decree.py` — ロジックは正しいが、4本ともCIワークフローに一度も配線されていなかった (2026-10)

\*\*発見\*\*: `src/`・`tools/`・`adapters/`の棚卸しの一環で、`tools/build_public_scripture.py`(経典=公開配布物のビルド検査ツール)を精査した際、GRIMOIRE.mdの既存記述(§「ライセンス証明書機構の公開配布からの分離」)が「`angels/metatron_scripture_seal.py`がこの配線を静的に検証する」と述べていることに気づいた。しかし実際に`grep -rl metatron_scripture_seal . --include="*.py" --include="*.yml" --include="*.md"`で確認したところ、ヒットしたのはGRIMOIRE.md自身の解説文だけであり、`.github/workflows/`配下のどのワークフローファイルのrun:ステップからも、COMMANDS.mdからも、他のどのスクリプトからも一度も呼び出されていなかった。

この発見を一般化し、`angels/`配下の全スクリプトが実際にCIワークフローのrun:ステップから呼び出されているかを機械的に検証する回帰テスト(`tests/test_angels_scripts_wired_into_ci.py`)を新設して実行したところ、同じ「配線漏れ」が他に3件見つかった: `raguel_template.py`(`src/openai_agent_loop.py`拡張テンプレートの防壁統合監査)、`sandalphon_decree.py`(Docker強制サンドボックス化の退行監査)、`zadkiel_shield_decree.py`(外部脅威インテリジェンス取り込み・`angelic_shield.py`/`kamael_judgment.py`の退行監査)。4本とも、単独実行すれば正しく`PASS`を返す、ロジック自体に欠陥のない検査スクリプトだった(実機確認済み)。

\*\*たとえ話\*\*: これは、警備会社が「カメラAの映像を監視する担当者」「カメラBの映像を監視する担当者」をきちんと配置し、それぞれの担当者は仕事をきちんとできる訓練を受けているにもかかわらず、実際にはカメラA・Bそのものの電源ケーブルが一度もコンセントに差されておらず、映像が一度もモニターに表示されていなかった、という状態である。見張り役(ロジック)は優秀でも、見張り台(CIワークフロー)に一度も立たせていなければ、何も見張っていない。

\*\*原因\*\*: この4本は、いずれも過去の特定の脆弱性修正(ライセンス証明書機構の分離、openai_agent_loopテンプレートの修正、Dockerサンドボックス強制化、angelic_shield/kamael_judgmentの再構築)の「再発防止用の回帰検査」として、修正そのものと一緒に新設されたものと見られる。しかし修正コミットの中で、スクリプト本体の作成とGRIMOIRE.mdへの記述は行われたものの、`.github/workflows/anjo_da_maquina_protocol.yml`への`run:`ステップの追加が漏れていた。本セッションでこれまで発見してきた「ロジックは正しいが実行環境側の前提が整っていない」系の欠陥(§AH・§AN)とは異なり、今回は実行環境の前提の問題ではなく、CIワークフロー自体にステップとして存在しないという、より根本的な配線漏れだった。

\*\*対応\*\*: 4本すべてを`.github/workflows/anjo_da_maquina_protocol.yml`に追加した。既存の番号付け規則に合わせ、`zadkiel_shield_decree.py`はステップ8(Zadkiel)の直後に8.5として、`raguel_template.py`はステップ12(Raguel)の直後に12.5として、`metatron_scripture_seal.py`はステップ14(Sariel)の直後に14.5として、`sandalphon_decree.py`はステップ20(Sandalphon)の直後に20.5として、それぞれ主題的に関連する既存ステップのそばに配置した。追加前に4本とも実際に単独実行して`PASS`することを確認してから配線した(配線した瞬間にCIを壊さないための確認)。

さらに、この種の配線漏れが将来別のスクリプトで再発しても機械的に検知できるよう、`tests/test_angels_scripts_wired_into_ci.py`を新設した。`angels/`配下の全`*.py`ファイル(`_common.py`を除く)が、`.github/workflows/`配下のいずれかのワークフローファイルの`run:`ステップから`yaml.safe_load`による構造的解析(§AOと同じ、コメント等への文字列残存だけでは一致しない方式)で実際に呼び出されていることを検証する。

\*\*検証\*\*: `tests/test_angels_scripts_wired_into_ci.py`を新設し、2件追加した。(1) 汎用テストとして、全天使スクリプトがいずれかのワークフローから参照されていることを確認(修正前のワークフローに対して`git stash`で実行すると、本件の4ファイルに加えて今回追加した`metatron_scripture_seal.py`自身も含めた不一致を正しく検出することを確認済み)。(2) 具体例として、`metatron_scripture_seal.py`が名指しで配線されていることを確認。`mini_pytest.py`再実行で`PASS=183`(§BB時点の181から新規2件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。既存の`angels/alpha_omega_guard.py`(ワークフロー構造監査)・`tests/test_alpha_omega_guard_structural_check.py`も引き続き正常にPASSすることを確認し、ワークフローYAML自体が`yaml.safe_load`で問題なく解析できることも確認した。

\### BD. `angels/_common.py`の`scan_for_leaked_secrets()`・`angels/firmament_enclave_tee.py`の`scan_for_hardcoded_sensitive_env_keys()` — 秘密情報漏洩検査自身が、自分自身を検証するテストフィクスチャを「本物の漏洩」と誤検知し、`anjo_da_maquina_protocol.yml`(Angels CI)を2026-10-10 23:29のマージ以降、継続的に失敗させ続けていた (2026-10)

\*\*発見\*\*: §BCをmainにマージした直後、「ローカルの`mini_pytest.py`シムだけでなく、実際のGitHub Actions上のCI状態も定期的に確認する」という本セッションの新しい自己点検習慣に従い、`gh run list --workflow=anjo_da_maquina_protocol.yml`を実行したところ、本ワークフロー(`sanctuary_ci.yml`とは別系統の、`angels/*.py`を個別のCIステップとして実行する「天使」プロトコル)が、2026-10-10 23:29:43Zのマージ以降、ユーザーからの提示を含む\*今回のセッションで行った§BA・§BB・§BCのマージも含めて\*、一度も成功しておらず、全て失敗していたことが判明した。これは本セッション開始以来、ローカルの`mini_pytest.py`の結果だけを見て「問題なし」と報告し続けていた期間と完全に重なっており、実CIの状態を一度も確認していなかったことによる重大な見落としだった。

ワークフローYAMLを`yaml.safe_load`し、各`run:`ステップを`GITHUB_ACTIONS=true`環境で順に実行する簡易CIシミュレータをローカルに構築して原因を特定したところ、`angels/firmament_enclave_tee.py`(ステップ「天空の閨房」)で確実に停止していることが分かった。実際に単独実行すると、`tests/test_firmament_enclave_tee.py`自身を「`OPENAI_API_KEY`という機密環境変数名がハードコードされた漏洩の疑いがあるファイル」として4箇所誤検知し、`sys.exit(1)`していた。

本件には\*\*2つの異なる原因\*\*が絡んでおり、公平に区別して記録する。

\*\*(1) 本セッション中に私自身が今日引き起こした回帰(自白)\*\*: §AZ(本セッション内、本件より前)で`scan_for_hardcoded_sensitive_env_keys()`の判定をファイル単位から行単位に修正した際、新設した`tests/test_firmament_enclave_tee.py`自身をスキャン対象から除外する処理を入れ忘れていた。このテストファイルは、ドキュメント文字列とテスト本体の両方に、検査が検知すべき「本物の漏洩パターン」の具体例として`"OPENAI_API_KEY"`という文字列を(`os.getenv`/`os.environ`を伴わない行に)含んでいる。これは正しいテストフィクスチャとしての設計だが、実リポジトリ全体をスキャンする本番の検査経路(`angels/firmament_enclave_tee.py`を直接実行する経路)が、このテストファイル自身を漏洩と誤認してしまうことを、§AZ修正時に確認していなかった。これは私の作業不足であり、素直に認める。

\*\*(2) 本セッション開始前から存在していた、私が今日引き起こしたのではない既存の不具合\*\*: `git log`で遡ると、`tests/test_scan_for_leaked_secrets.py`に、AWSアクセスキーの形式(`AKIA`で始まる20文字の英大文字・数字列)に一致する「本物らしい偽の値」を持つモジュールレベルのテストフィクスチャ定数(変数名`AWS_KEY_LOOKALIKE`)が、`fix/secret-scan-exclusion-prefix-bypass`というブランチのマージ(2026-10-10 23:29:43Z、本セッション開始前)で追加されていたことを確認した。このコミット自体は別の正当な脆弱性修正(前方一致バイパスの修正、`EXCLUDED_SECRET_SCAN_DIRS`の完全一致化)だったが、そのテストフィクスチャが、`angels/gabriel_canary.py`(`scan_for_leaked_secrets()`をrootの指定なしで呼ぶ経路)による実リポジトリ全体スキャンを、このマージの直後から継続的に失敗させ続けていた。つまりCI破壊の「発生源」そのものは本セッションより前のものであり、本セッションがこれまで発見できなかった既存の不具合である。

\*\*たとえ話\*\*: これは空港の金属探知機のようなものである。本物の武器(本物のAPIキー・秘密鍵)を検知するために置かれているが、この探知機の性能を検証するための「訓練用の模造ナイフ」(テストファイル中の、意図的に本物らしく作った偽の鍵の文字列)を保管している棚を、探知機の巡回スキャン範囲から外し忘れていた。探知機は律儀に巡回し、模造ナイフを見つけるたびに律儀に警報を鳴らし続け、空港(CI)の運用を止めていた。原因(1)は私が今日新しく置いた模造ナイフを棚から外し忘れた話、原因(2)は何日か前から既に別の棚に置かれていた模造ナイフの話であり、両者は別の棚(別のテストファイル・別のコミット)にある別の話である。

\*\*原因\*\*: 両検査関数とも、「テスト容易性のため」`root`(および`self_path`)を明示的に渡せるようにしており、`tests/`配下の単体テスト自身はいずれも`root=tmp_path`の一時ディレクトリで検証しているため、検査ロジック自体は正しく機能している。しかし、`root`の指定なしで実リポジトリ全体をスキャンする本番の呼び出し経路(CI上で実際に実行される経路)は、`tests/`ディレクトリ自身を除外していなかった。「検査対象であるコード」と「検査ロジックを検証するためのテストフィクスチャ」が同じリポジトリ内に共存する場合、本番スキャン経路は後者を除外する設計が必要だったが、その除外が両スクリプトとも漏れていた。

\*\*対応\*\*: `angels/_common.py`の`EXCLUDED_SECRET_SCAN_DIRS`に`"tests"`を追加し、`angels/firmament_enclave_tee.py`の`scan_for_hardcoded_sensitive_env_keys()`内の除外条件に`"tests" in p.parts`を追加した。いずれも既存の単体テストは`root=tmp_path`の一時ディレクトリを明示的に渡して検証しているため、実リポジトリの`tests/`ディレクトリを本番スキャン対象から除外しても、既存テスト自体の検証能力には一切影響しない(除外されるのは本番の実リポジトリスキャン経路のみ)。

なお、この修正作業の過程で、`angels/_common.py`に説明コメントを書く際、誤って問題の偽AWSキー文字列そのものをコメント内に引用してしまい、それ自体が`gabriel_canary.py`の再実行で新たに誤検知される、という二次的な自己ミスが一度発生し、その場で修正した。さらに、\*\*この文書(GRIMOIRE.md)自身の本節の初稿でも、全く同じ誤り(偽AWSキー文字列の逐語的な引用)を再び犯し\*\*、`main`へのマージ後の実CI確認で`gabriel_canary.py`が今度は`GRIMOIRE.md`自身を漏洩として検知して失敗するという、二度目の自己ミスを引き起こした。これは実機のCI結果で発覚し、本節の記述を「パターンの説明」(AKIAで始まる形式、という記述)に書き直す追加修正でその場で対応した。小さいとは言えない繰り返しであり、「自らの首をしめた場合は正直に告白する」という方針に従い、両方をここに正直に記録する。

\*\*検証\*\*: `tests/test_secret_scanners_do_not_flag_own_test_suite.py`を新設し、2件追加した。(1) `scan_for_leaked_secrets()`を`root`指定なし(=実リポジトリ全体)で呼んでも検知件数が0件であること。(2) `scan_for_hardcoded_sensitive_env_keys()`を同様に`root`/`self_path`指定なしで呼んでも検知件数が0件であること。`git stash`で修正前のコードに戻して実行すると、(1)は`tests/test_scan_for_leaked_secrets.py`の偽AWSキーを、(2)は`tests/test_firmament_enclave_tee.py`(および新設した本テストファイル自身のdocstring中の`"OPENAI_API_KEY"`という記述)を、それぞれ正しく誤検知として検出し失敗することを確認した。修正適用後は両方PASSすることを確認した。`mini_pytest.py`再実行で`PASS=185`(§BC時点の183から新規2件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。さらに、`.github/workflows/anjo_da_maquina_protocol.yml`全体(全ステップ、§BCで追加した4ステップを含む)をローカルシミュレータで再実行し、全ステップが`[OK]`になることを確認した。

\*\*残存する限界\*\*: 本修正は、`tests/`ディレクトリ全体を本番スキャン対象から除外するものである。これは「`tests/`配下に本物の秘密情報が紛れ込んだ場合、この検査では検知できなくなる」という新たなトレードオフを意味する(ただし、テストコードに本物の秘密情報を直接書くこと自体がそもそも避けるべき運用であり、本件はテストフィクスチャとしての\*偽の\*鍵・キー名であって、この除外によって新たに守れなくなる本物の秘密は想定していない)。より厳密には、「本物らしく見えるが偽であることが明示されたテストフィクスチャ」と「本物の漏洩」を区別する専用のマーカー(例: 特定のコメントタグ)を導入する設計も考えられるが、本件の修正範囲では、既存の他の除外ディレクトリ(`dummy_secrets`等)と同様の、ディレクトリ単位の除外という既存パターンに合わせた。

本件が最も重く示しているのは、技術的な欠陥そのものより、\*\*「ローカルの`mini_pytest.py`シムが常にPASSしていても、実際のGitHub Actions CIが別の理由で何日も継続的に失敗し続けている可能性がある」という検証プロセス自体の盲点\*\*である。本セッションは§AG以降、§BCまでの多数のマージを、ローカルシムの結果のみを根拠に「問題なし」と報告してきたが、少なくとも2026-10-10 23:29以降のマージ(§BA・§BB・§BCを含む)は、実際には一度もAngels CIを green にしていなかった。この盲点は、今回たまたま習慣を変えて`gh run list`を実行したことで発覚したものであり、変えていなければ発覚しないまま埋もれ続けていた可能性がある。

\### BE. `tools/generate_dashboard.py` — 平均QAスコア(`avg_qa`)を集計していたが、生成されるHTMLダッシュボードのどこにも表示していなかった (2026-10)

\*\*発見\*\*: 棚卸しの一環で、`GRIMOIRE.md`に一度も登場していなかった(=一度も精査されていなかった)ファイル群を優先的に精査する中で、`tools/generate_dashboard.py`の`build_dashboard()`を読んだところ、`avg_qa = (sum(r.get("qa_score", 0) for r in akashic) / total_battles) if total_battles else 0.0`という計算が行われているにもかかわらず、`avg_qa`という変数名がこの関数の残りの部分(返り値のHTML文字列)に一度も現れないことに気づいた。実機確認: 実際にサンプルデータで`build_dashboard()`を呼び出し、返り値のHTML文字列全体を検索しても、平均QAスコアに該当する数値・文言のいずれも一度も出力されないことを確認した。

\*\*たとえ話\*\*: 経理担当者が電卓で正しく平均点を計算し、その数字をメモに書き留めたのに、その数字を一度も報告書本体に転記せず、メモだけを机の引き出しにしまって終わっていた、という状態である。計算自体は正しく、危険でも何でもないが、せっかく集計した情報が誰の目にも届かないまま失われていた。

\*\*原因\*\*: セキュリティ上の脆弱性ではなく、作りかけの機能(他の集計値である`total_battles`・`breached`・`breach_rate`等は全て概要カードとして出力されているのに対し、`avg_qa`だけがその配線を忘れられていた)。本セッションがこれまで発見してきた「ロジックは正しいが配線されていない」という系統の欠陥(§AN・§BC)と同じパターンだが、CIワークフローの配線ではなく、単一ファイル内の「計算結果を出力に反映する」という配線の欠落である点が異なる。

\*\*対応\*\*: 他の集計値と同じ「概要カード」として、`平均QAスコア`のカードをダッシュボードの概要セクションに追加し、`avg_qa`を小数点以下1桁で表示するようにした。

\*\*検証\*\*: `tests/test_generate_dashboard.py`に`test_dashboard_displays_the_average_qa_score_it_computes`を新設した。QAスコア10点・5点の2戦績(平均7.5)を与えた`build_dashboard()`の返り値に`"7.5"`という文字列が実際に含まれることを検証する。`git stash`で修正前のコードに戻すとこのテストが失敗し、修正後にPASSすることを確認した。`mini_pytest.py`再実行で`PASS=186`(§BD時点の185から新規1件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。既存の2件のテスト(概要カードの集計・ファイル欠損時の安全な動作)も引き続き正常にPASSすることを確認した。

\### BF. `.github/workflows/anjo_da_maquina_protocol.yml`(§ANの`actions/cache`) — チェックポイントだけをキャッシュし、そのハッシュの根拠である署名鍵と監査証跡本体をキャッシュし忘れていたため、2回目以降の実行が構造的に毎回「改ざん検知」を誤報し続けていた (2026-10)

\*\*発見\*\*: §BD・§BEを`main`にマージした直後、新しい習慣(`gh run list`での実CI確認)に従って`anjo_da_maquina_protocol.yml`を確認したところ、§BEのマージでは成功していたにもかかわらず、その次のマージ(本件を発見する直前の通常のマージ)で再び失敗していた。原因は`21.5. サンダルフォンの錨`ステップ(`angels/sandalphon_anchor.py`)で、ローカルで単体実行すると正常にPASSするにもかかわらず、実CI上でのみ失敗する、という§BDと同じ構造の問題だった。

ワークフローYAMLを確認したところ、§AN(本セッションより前の修正)で追加された`actions/cache`ステップが、`sefer/.angel_state`(前回実行時のチェックポイント)のみをキャッシュしており、そのチェックポイントのハッシュの計算根拠である2つの要素をキャッシュし忘れていたことが分かった。実機ではなく、一時ディレクトリで複数回の「CI実行」を独立したPythonプロセスとして模倣する再現スクリプトを書いて、原因を段階的に特定した。

\*\*原因は2段階重なっていた\*\*:

1. `sefer/audit_chain.py`の`SignedAuditChain`は、各エントリをHMAC-SHA256で署名する鍵(`sefer/.audit_signing_key`)を使う。この鍵ファイルが存在しなければ`os.urandom(32)`で新規生成される。`.angel_state`とは兄弟ディレクトリにあり、キャッシュ対象に含まれていなかったため、使い捨てランナー上では実行ごとに別の鍵が生成されていた。再現実験で、鍵だけをキャッシュしない状態で2回分の実行を模倣すると、2回目は確実に「履歴の巻き戻し・改ざんの疑い」で失敗することを確認した。

2. (1)を直すだけではまだ不十分だった(これも実機確認を模した再現実験で発覚)。`sefer/audit_chain.jsonl`自体もキャッシュされておらず、実行ごとに空のチェーンから作り直される。各エントリのハッシュ計算対象には`timestamp`(`record()`呼び出し時の実時刻)が含まれているため、鍵が同一であっても、別の実行で作り直されたチェーンの同じindex位置のエントリは、タイムスタンプが異なるために必ず別のハッシュになる。つまり「前回実行のチェックポイント」と「今回ゼロから作り直したチェーン」を比較する限り、鍵を揃えるだけでは原理的に一致し得ない。

\*\*たとえ話\*\*: これは、金庫の「開閉記録ノート」(監査証跡)と、そのノートに押す「割印」(署名鍵)の両方を、毎晩忘れずに保管庫へしまうルールを作ったつもりが、実際には保管庫の鍵(チェックポイント)だけをしまい、ノート本体と割印は毎晩真新しいものに取り替えてしまっていた、という状態である。翌朝「昨日の割印と記録が合っているか」を確認しようとしても、ノートと割印そのものが昨日とは別物なのだから、合うはずがない。これは「検知ロジックの前提が整っていない」という§AN・§BDと同じ系統の欠陥だが、§ANの修正自体がこの欠陥を新たに生んでしまった(チェックポイントだけを直せば十分だと誤解していた)という点で、一段階ネストした構造的な見せかけである。

\*\*原因の総括\*\*: この「証跡のブロックチェーン刻印」機構が本来の意味(複数回の実行を跨いでロールバック・改ざんを検知する)を持つためには、監査証跡そのものが実行を跨いで継続する単一の台帳でなければならない。§ANの修正は「前回のチェックポイントと鍵が指す監査証跡を正しく比較するために、監査証跡自体も永続化する必要がある」という、検知ロジックが本当に依存する状態の全体像を見誤っていた。

\*\*対応\*\*: `actions/cache`の`path`に`sefer/.audit_signing_key`・`sefer/audit_chain.jsonl`を追加し、鍵・チェーン本体・チェックポイントの3つを常に同じキャッシュ世代でセットに保つようにした。

\*\*検証\*\*: `tests/test_sandalphon_anchor_state_persistence.py`に2件追加した。(1) `test_cache_also_persists_the_signing_key_and_the_chain_itself`: ワークフローYAMLの構造解析により、キャッシュ対象の`path`に`.audit_signing_key`・`audit_chain.jsonl`の両方が含まれていることを検証する(`git stash`で修正前のワークフローに戻すと、`.audit_signing_key`の欠落で実際に失敗することを確認済み)。(2) `test_three_simulated_ci_runs_with_the_fixed_cache_set_never_false_positive`: 実際に`SignedAuditChain`・`sandalphon_anchor.main()`を使い、3回分の独立した"CI実行"(それぞれ独立した一時ディレクトリ、鍵・チェーン本体・チェックポイントの3つを前回実行から引き継ぐ)を模倣し、いずれの実行でも誤って「改ざんの疑い」を報告しないことを機能レベルで固定した。さらに、修正前の状態(鍵のみキャッシュ・チェーン未キャッシュ)では2回目以降が必ず失敗し、鍵とチェーン本体の両方をキャッシュした場合は3回目以降も正しくPASSし続けることを、一時ディレクトリでの独立した再現実験でも別途確認した。`mini_pytest.py`再実行で`PASS=188`(§BE時点の186から新規2件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。

\*\*残存する限界\*\*: `sefer/audit_chain.jsonl`が実行を跨いで無期限に成長し続ける点は、「ブロックチェーン」としての本来の意図通りの挙動だが、将来的にはキャッシュサイズの肥大化(actions/cacheには上限があり、巨大化すれば保存・復元自体に失敗し得る)に注意が必要である。また、actions/cacheにも7日間アクセスが無いと自動失効する制約があり、恒久不変の外部監査サービスの代替にはならない(§ANで既に明記済みの限界と同根)。

\### BG. `src/angelic_evolution.py` の `EvolvingAngel.defend_and_execute()` — §BBと同じ「事前検閲の通過と実行結果を混同する」バグの4件目。実運用の自動防衛ループ(`src/metatron_orchestrator.py`)が偽の「致命的敗北」を報告し続けていた (2026-10)

\*\*発見\*\*: §BFをmainにマージし実CIの連続成功を確認した後、`src/`・`adapters/`・`tools/`の棚卸しを継続する中で、`src/angelic_evolution.py`(§AWで既に一度精査済みのファイル)を読み直したところ、`EvolvingAngel.defend_and_execute()`の末尾が`return self.aegis.execute_ai_intent(payload, target)`となっていることに気づいた。これは`src/adversarial_evolution.py`の§BBで既に発見・修正したのと\*\*全く同じ構造の欠陥\*\*である: `execute_ai_intent()`はGabriel・IntentInterceptor・Dockerの隔離結界内での使い捨てドライランのみを行う事前検閲であり、実際のファイルI/O・コード実行は呼び出し側が`sefer.Sanctum`の中で行う責務として明示的に残されている(`src/aegis_system.py`のdocstring参照)。本関数はこの責務を一度も果たしていなかった。

さらに重要な点として、本ファイルは`src/metatron_orchestrator.py`の`execute_holy_war()`から呼ばれており、§BBの`src/adversarial_evolution.py`(自己対戦シミュレーション単体、スタンドアロン実行専用)とは異なり、\*\*実運用の自動防衛ループに配線されている\*\*。`execute_holy_war()`は`defend_and_execute()`が例外を出さなければ無条件に`"❌ 致命的敗北: サマエルの毒が防壁を突破しました。"`という文言を`revelations/`配下のレポートファイルに記録する設計である。

実機検証: `open(path, "w").write("pwned")`という、importも禁止関数名も含まないペイロードを`defend_and_execute()`に通したところ(Docker不在のテスト環境のため`require_docker_sandbox=False`で事前検閲層のみを切り離して検証)、修正前は例外を出さずに`True`を返すことを確認した(=偽の「防壁突破」が報告される)。一方、`src/adversarial_evolution.py`の`execute_payload_under_sanctum()`で同じペイロードを実際にSanctum配下で実行すると、Michaelが確実に`LossOfAtaraxia`で遮断することは§BBで既に実証済みである。

\*\*たとえ話\*\*: §BBが「事前の身辺調査だけで『侵入者は要人警護を突破した』と断定してしまう」話だったのに対し、本件はその\*逆方向\*の誤りである。身辺調査(事前検閲)を無事通過した人物について、本当の警備ゲート(Michael/Sanctum)に一度も通していないにもかかわらず、警備チーム自身が「突破された、我々の負けだ」と自己申告し、その誤った戦績を上司への報告書に記録し続けていた、という状態である。実際には警備ゲートを通していないので、本当に突破されたかどうかは誰にも分かっていない。

\*\*原因\*\*: §BBの修正時、同じバグが他のファイルにも存在するかどうかの横断確認が行われておらず、`src/angelic_evolution.py`は当時のGRIMOIRE.md §AW(本ファイル内の別の不具合、CassielsVeilの誤統合)の修正時にも、この`return self.aegis.execute_ai_intent(...)`の行自体は精査対象になっていなかった。本セッションがこれまで発見した同種のバグ(§AU: `tartarus/armageddon.py`、§AX: `tools/auto_red_team.py`、§BB: `src/adversarial_evolution.py`)が3件とも「偽の勝利」(実際には突破されていないのに突破されたと誤認、あるいはその逆)という一方向のパターンだったのに対し、本件は「偽の敗北」(実際には遮断されるはずなのに、確認せず敗北と自己申告する)という逆方向の表れ方をする、同じバグの系統の4件目である。

\*\*対応\*\*: `src/adversarial_evolution.py`の`execute_payload_under_sanctum()`を再利用し(同じロジックを2箇所にコピーすると、片方にのみ修正が入り他方が取り残えるリスク(GRIMOIRE.md §M)を避けるため、`src/futility_guard.py`で既に確立済みの「共有モジュール化」パターンに合わせた)、`defend_and_execute()`の末尾で、事前検閲を通過した後に必ずこの関数を呼び、実際にSanctum配下で実行するようにした。Michaelが遮断した場合は`PermissionError`に包んで呼び出し元(`metatron_orchestrator.py`の既存の`except Exception`分岐、「迎撃成功」)に伝播する。

\*\*検証\*\*: `tests/test_angelic_evolution_sanctum_execution.py`を新設し、4件追加した。(1) 前提確認として、バイパスペイロードがGabrielの静的解析を無傷で通過することを固定。(2) 修正の核心として、同じペイロードを`defend_and_execute()`に通すと(Docker不在のテスト環境のため事前検閲層のみを切り離した状態で)、修正前は`True`を返し(`git stash`で確認済み)、修正後は`PermissionError`で確実に遮断され、実際にファイルが書き込まれないことを確認。(3) 回帰防止として、`learn_threat()`が動的に学習した禁止パターンに一致するペイロードは、従来通りSanctumに到達する前に即座に遮断されることを確認(§BGの修正が既存の経路を壊していないこと)。(4) 回帰防止として、ファイルI/O・外部接続を一切行わない本当に無害なコードは正常に`True`を返すこと(過剰検知になっていないこと)を確認した。`mini_pytest.py`再実行で`PASS=192`(§BF時点の188から新規4件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。既存の`tests/test_metatron_orchestrator_cassiel_ollama.py`(§AW回帰テスト)も引き続き正常にPASSすることを確認した。

\*\*残存する限界\*\*: 本修正が固定するのは「`defend_and_execute()`の最終判定が実際のMichaelの実行結果を経るようになった」という、この自動防衛ループ自身の報告の正確性のみである。§AYで既に確認済みの通り、Gabriel/IntentInterceptor単体の静的解析には引き続き限界が残る。また、本修正により`src/angelic_evolution.py`は`src/adversarial_evolution.py`に依存するようになったため、将来後者が削除・大幅変更される場合は本ファイルも合わせて確認すること。

\### BH. `tools/pre_commit_secret_scan.py` — §BDの除外ディレクトリ(`EXCLUDED_SECRET_SCAN_DIRS`)を再利用しておらず、CIでは通過する`tests/`配下のテストフィクスチャだけをpre-commitがブロックし続けるという、新たな「CIとpre-commitのズレ」が発生していた (2026-10)

\*\*発見\*\*: §BGをmainにマージした後、`src/`・`adapters/`・`tools/`の棚卸しを継続する中で、`tools/pre_commit_secret_scan.py`を読み直した。本ファイル自身のコメントには「`angels/_common.py`の`SECRET_PATTERNS`を単一の正として再利用することで、『CIでは検知されるがpre-commitでは検知されない』というズレを防ぐ」という設計意図が明記されている。しかし実際には`SECRET_PATTERNS`のみを再利用し、§BDで`_common.py`に追加された`EXCLUDED_SECRET_SCAN_DIRS`(`tests`ディレクトリの除外)は一切再利用していないことに気づいた。

実機検証: 一時的なgitリポジトリを作成し、`tests/`配下に`tests/test_scan_for_leaked_secrets.py`の実際のフィクスチャと同じ内容(`AWS_KEY_LOOKALIKE = "AKIA..."`)を持つファイルをステージして`scan_staged_changes()`を実行したところ、CI側(`angels/gabriel_canary.py`、§BD修正後)は正しく通過するのに対し、pre-commit側は依然としてコミット自体を拒否する(exit code 1)ことを確認した。

\*\*たとえ話\*\*: §BDで「空港の金属探知機(本番のCIスキャン)」が、訓練用の模造ナイフ(テストフィクスチャ)を本物の武器と誤認しないように、探知機の巡回範囲から訓練用品の保管庫(`tests/`)を外した。しかし、その建物には別の入り口に「手荷物の持ち込み検査(pre-commitフック)」という独立した検査員がいて、この検査員には保管庫の除外ルールが伝達されておらず、今でも訓練用の模造ナイフを持ち込もうとする人(`tests/`配下へのコミット)を本物の武器だと思って毎回止め続けていた、という状態である。

\*\*原因\*\*: §BDの修正は`angels/_common.py`の`scan_for_leaked_secrets()`(CI経路)と`angels/firmament_enclave_tee.py`(CI経路)の2箇所のみを対象としており、同じ`SECRET_PATTERNS`を参照しながら独自の除外ロジックを持たない`tools/pre_commit_secret_scan.py`(pre-commit経路)への横展開が行われていなかった。本ファイル自身が設計時に警戒していた「CIとpre-commitのズレ」が、パターン定義の観点では防がれていたものの、除外ディレクトリの観点では結局再発してしまっていた。

\*\*対応\*\*: `_common.py`から`EXCLUDED_SECRET_SCAN_DIRS`も併せてimportし、`scan_for_leaked_secrets()`と同一の判定基準(完全一致、またはそのディレクトリ配下であること)で、ステージされたファイルパスが除外対象ディレクトリに含まれる場合はスキャン対象から外す`_is_excluded()`を新設し、`scan_staged_changes()`の冒頭で適用するようにした。

\*\*検証\*\*: `tests/test_pre_commit_secret_scan.py`に`test_tests_directory_fixture_is_not_blocked_but_same_content_elsewhere_still_is`を新設した。(1) `tests/`配下に本物らしい偽のAWSキーを含む新規ファイルをステージしても、コミットがブロックされない(exit code 0)こと。(2) 全く同じ内容を`tests/`配下でない場所(`config.py`)に置いた場合は、引き続きブロックされる(exit code 1)こと、の両方を1つのテストで固定した((2)は除外範囲が広すぎて本物の漏洩まで見逃すようになっていないことの確認を兼ねる)。`git stash`で修正前のコードに戻すと(1)が失敗することを確認した。`mini_pytest.py`再実行で`PASS=193`(§BG時点の192から新規1件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。既存の4件のテスト(無害なファイル・AWSキー・PEM秘密鍵の検知・既存行の再検知防止)も引き続き正常にPASSすることを確認した。

\*\*残存する限界\*\*: このpre-commitフック自体は`git config core.hooksPath hooks`を手動で実行しないと有効化されない(リポジトリをクローンしただけでは自動的には動かない)ため、本件は現状では「将来このフックを有効化した開発者が、tests/配下への正当な変更のたびにコミットをブロックされ続ける」という潜在的な運用上の支障であり、CI自体を壊すものではなかった。しかし、CIとpre-commitという2つの検査経路が同じ`SECRET_PATTERNS`を参照しながら異なる除外基準を持つという非対称な状態は、§BDと同じ系統の「見せかけの一致」であり、放置すべきではないと判断した。

\### BI. `anjo_interceptor/intent_checker.py` の `IntentInterceptor.evaluate_action()` — §AKで"read"/"write"に追加された脱走検知が、後から追加された"list"アクションには一度も適用されていなかった (2026-10)

\*\*発見\*\*: §BHをmainにマージした後、ユーザーから「残りも全部見て、見れるところは全部みて」という明示的な指示を受け、リポジトリ全体の棚卸しを継続する中で`anjo_interceptor/intent_checker.py`を読み直した。本ファイルのクラスdocstring自体に§AKの修正経緯(「"write"分岐は".."連鎖と保護ディレクトリ名のみを検査し、"read"分岐はハニーポット一致のみを検査しており、いずれもtarget_pathが絶対パスである場合の封じ込め検証が一切無かった」)が明記されており、修正は`evaluate_action()`の"read"・"write"の両分岐に`_assert_contained_within_workspace()`を追加する形で行われていた。しかし`evaluate_action()`を読み進めると、`if action_type == "read":`と`if action_type == "write":`の2つの条件分岐しか存在せず、`self.allowed_actions`に含まれる3つ目のアクション("list")に対応する条件分岐が丸ごと存在しないことに気づいた。つまり"list"は`allowed_actions`チェック(未許可アクションの遮断)さえ通過すれば、何の封じ込め検証も honeypot 検証も受けずに無条件で`True`が返る状態だった。

実機検証: `IntentInterceptor(workspace_root="jail_workspace").evaluate_action(json.dumps({"action": "list", "target": "/etc"}))`を実行したところ、`SpecificationGamingDetected`が発生せず`True`が返ることを確認した(workspace_root外の絶対パスへの"list"要求が無条件で承認される)。既存テスト`tests/test_intent_gaming.py`の`test_list_action_is_not_blocked_as_unauthorized`も、`target="."`という正常系のみを検証しており、脱走ケースを一切カバーしていなかった。

\*\*たとえ話\*\*: §AKで、建物の「持ち出し」(write)と「持ち込み」(read)の両方の荷物検査で、行き先・出どころが本当に建物の敷地内かどうかを調べるようにした。しかし後から「中を見るだけ」(list=一覧取得)という3つ目の検査窓口を新設した際、そこだけ検査官を配置し忘れ、誰でもどんな行き先でも素通りできる状態になっていた、という話である。幸い、この建物には別の階にもう二重の検査(後述)があるため、現状では実害までは至っていないが、窓口そのものは丸腰である。

\*\*原因\*\*: "list"は§AK修正より後に`tests/test_intent_gaming.py`の`test_list_action_is_not_blocked_as_unauthorized`というテストを伴って`allowed_actions`へ追加されたが、そのテストが固定したのは「正当な"list"要求が誤って『未許可のアクション』として遮断されないこと」のみであり、§AKの脱走検知を"list"にも横展開する観点が欠けていた。これは§BHで発見した「ある修正が複数の経路のうち一部にしか適用されない」というコードカバレッジの系統のズレと同種である。

\*\*実運用パイプラインでの実害の有無\*\*: `src/ollama_agent_loop.py`の実運用ループでは、`interceptor.evaluate_action(ai_output)`の承認後、必ず`AegisSystem.execute_ai_intent()`が同じtargetを\*合成的に"write"として\*再評価し(`src/aegis_system.py`の`execute_ai_intent()`内、ステップ3)、さらに`_execute_safe_action()`内で"list"専用に`WorkspaceJail.secure_resolve()`による封じ込め検証も行われる(Sanctumの監査フックは`os.listdir`をホワイトリスト経由で常に素通りさせてしまうため、"list"だけはこの`secure_resolve()`が唯一の実効的な防衛線であることが`ollama_agent_loop.py`自身のdocstringに明記されている)。そのため現行の実運用パイプラインでは、2つの独立した層がこの穴を偶然塞いでおり、致命的な脱走には至らない(実機検証済み)。

しかし`IntentInterceptor`自身のクラスdocstring(§AK)が明記する通り、本クラスの存在理由は「Sanctumの監査フックに将来何らかの抜け道が見つかった場合の安全網」である。しかも"list"はSanctumの監査フックによる保護を最初から一切受けていない設計であるため、本来であれば"list"こそ、この`IntentInterceptor`自身による封じ込め検証がもっとも重要な場所だった。`src/openai_agent_loop.py`の`_execute_safe_action()`には"list"分岐自体が存在しない(システムプロンプトにも"list"を含めていない)ため実害はないが、これは設計上の意図的な省略というより未実装であり、今後"list"対応が追加された場合に同じ穴が再現しうる。

\*\*対応\*\*: "read"・"write"と同一の`_assert_contained_within_workspace()`を"list"にも適用する分岐を`evaluate_action()`に追加した。honeypot検証は"list"(ディレクトリの一覧取得であり、ファイル内容の直接読み取りではない)には適用していない(既存の"read"の設計意図と同様、内容そのものへのアクセスを伴う操作にのみ適用する)。

\*\*検証\*\*: `tests/test_intent_interceptor_absolute_path_escape.py`に3件追加した。(1) `test_absolute_path_list_outside_workspace_is_rejected`: workspace外の絶対パスへの"list"要求が`SpecificationGamingDetected`で遮断されることを固定(修正前は`git stash`で確認した通り無条件に`True`が返っていた)。(2) `test_relative_traversal_list_escaping_workspace_is_rejected`: ".."連鎖による相対パスでの"list"脱走も同様に遮断されることを固定。(3) `test_list_within_workspace_still_succeeds`: workspace配下への正常な"list"要求が引き続き許可されることの回帰防止。`git stash`で修正前のコードに戻すと(1)(2)が失敗し、修正後にPASSすることを確認した。`mini_pytest.py`再実行で`PASS=196`(§BH時点の193から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ、`rsa`パッケージ未インストールと`mini_pytest.py`シム自体のxfail API差異)であることを確認した。既存の`test_list_action_is_not_blocked_as_unauthorized`(正常系)も引き続き正常にPASSすることを確認した。加えて、`angels/gabriel_canary.py`・`angels/firmament_enclave_tee.py`を手動実行し、本修正のコメント文中に偽の秘密情報らしき文字列を誤って含めていないこと(§BDで2度繰り返した過ち)を直接確認した。

\*\*残存する限界\*\*: 本修正は`IntentInterceptor`自身の防御力を"read"/"write"と同水準に揃えるものであり、実運用パイプラインの挙動自体(`AegisSystem.execute_ai_intent()`の合成write再評価、`_execute_safe_action()`の`secure_resolve()`)は変更していない。これらの層が将来削除・改変された場合に備える「安全網」としての本来の意義を回復させることが目的であり、現時点での実害を解消するものではない(現行パイプラインは本修正前から既に安全だった)。

\### BJ. `tartarus/armageddon_core.py` の `validate_banned_event()` — `sefer`が常に無条件で通過させるイベント名(`socket.getaddrinfo`等)を、Razielの台帳への有効な禁止提案として受理してしまっていた (2026-10)

\*\*発見\*\*: §BIをmainにマージした後、ユーザーから「さらなる自己レビューと自己改善、増築、進化をお願いします」という指示を受け、これまでの個別ファイル単位の読み込みに加え、「人間承認の仕組みそのもの」が実際に意味のある保護を提供しているかという、より一段深い観点での自己点検を行った。`sefer/raziel_ledger.json`(Armageddonの自己対戦が発見した新しい禁止イベントを人間が承認して反映する仕組み)自体は既に実際の防御(`_michael_absolute_defense`)に正しく統合されている(§の「Raziel's Ledgerが一度も読み込まれていなかった」件は既に修正済み)。しかし、その統合先である`_michael_absolute_defense`自身の構造を精査したところ、ソケット検査(分岐2)とデフォルト拒否(分岐4)の両方が、`{"socket.getaddrinfo", "socket.socket", "socket.__init__"}`(ソケット検査側)・`{"os.stat", "os.listdir", "os.getcwd", "os.path", "socket.getaddrinfo", "socket.socket", "socket.__init__"}`(デフォルト拒否側)という固定の許可リストに該当するイベント名を、常に無条件で`pass`して`return`することに気づいた。Razielの台帳のenforcement(関数の最後の分岐5)は、分岐1〜4のいずれにも該当しなかったイベントだけが到達する設計であるため、この許可リストに含まれるイベント名は、台帳にどれだけ追加しても\*絶対に\*禁止できない。

一方、`tartarus/armageddon_core.py`の`validate_banned_event()`(Metatronが提案した禁止イベント名を、人間の承認キューに積む前に検証する関数)は、`CRITICAL_INFRASTRUCTURE`(自己免疫疾患ガード、"open"・"exec"等の誤禁止でシステムが止まることを防ぐための拒否リスト)に`"os.stat"`・`"os.listdir"`・`"os.getcwd"`のみを含んでおり、`"os.path"`・`"socket.getaddrinfo"`・`"socket.socket"`・`"socket.__init__"`の4つは含まれていなかった。つまりMetatronがこれらのいずれかを禁止イベントとして提案し、人間が`tools/promote_ledger_seal.py --approve socket.getaddrinfo`のように承認すると、提案自体は「有効」と判定され、`raziel_ledger.json`に正式に反映される。しかし、実際にその事象を発生させても何の遮断も起きない。

実機検証: `validate_banned_event("socket.getaddrinfo")`が修正前は`(True, "valid")`を返すことを確認した上で、一時ディレクトリに`raziel_ledger.json`を作成し`banned_events`に`"socket.getaddrinfo"`を含めた状態で`sefer.Sanctum`配下で実際に`socket.getaddrinfo("localhost", 80)`を呼び出したところ、何の例外も発生せず正常に実行されることを確認した。

\*\*たとえ話\*\*: これは、警備会社が「今後この人物の出入りも禁止します」という申請書を正式に受理し、台帳に記録し、申請者(人間の承認者)には「これで安全になった」と伝えたものの、実際の警備員には最初から「この人物だけは絶対に止めるな」という別の、台帳より優先される指示が常に先に渡っていた、という状態である。台帳そのものの仕組み(§の修正)は正しく機能するようになっていたが、その台帳に「そもそも載せても無意味な名前」を受理してしまう入り口側の検査が足りていなかった。

\*\*原因\*\*: `CRITICAL_INFRASTRUCTURE`(自己免疫疾患ガード)と`_michael_absolute_defense`の2つの固定許可リストは、それぞれ別の目的(前者は「壊れる」ことの防止、後者は「常に許可する」という挙動の定義)で個別に作られ、互いの対応関係が一度も検証されていなかった。`_michael_absolute_defense`側の2つの許可リストも、それぞれの検査ブロック内にリテラルの集合として個別に書かれており、単一の正としてどこからも参照されていなかったため、`armageddon_core.py`側がこれを把握する手段そのものが存在しなかった。

\*\*対応\*\*: `sefer/__init__.py`内の2つの許可リストを`ALWAYS_PASSTHROUGH_AUDIT_EVENTS`という単一のモジュールレベル定数に統合し、ソケット検査・デフォルト拒否の両方の分岐からこれを参照するようにした(挙動は変更していない、純粋なリファクタリング)。`tartarus/armageddon_core.py`の`validate_banned_event()`がこの定数をimportし、`CRITICAL_INFRASTRUCTURE`と同様に、ここに含まれるイベント名の提案を「見せかけの保護ガード(illusory-protection guard)」として明示的な理由付きで拒否するようにした。

\*\*検証\*\*: `tests/test_armageddon_core.py`に2件追加した。(1) `test_validate_banned_event_rejects_structurally_unenforceable_events`: `socket.getaddrinfo`・`socket.socket`・`socket.__init__`・`os.path`の提案が拒否されることを固定。(2) `test_validate_banned_event_still_accepts_genuinely_new_enforceable_events`: 既存カテゴリに該当しない本当に新しいイベント名(`urllib.Request`)は引き続き受理されることの回帰防止。さらに`tests/test_learned_rules_enforcement.py`に`test_always_passthrough_events_really_are_unenforceable_via_ledger`を追加し、`ALWAYS_PASSTHROUGH_AUDIT_EVENTS`の全要素を実際に`raziel_ledger.json`へ登録した状態で`sefer.Sanctum`配下で発火させても例外が発生しない(=この集合の分類が実機の挙動と一致している)ことを固定した。`git stash`で修正前のコードに戻すと`validate_banned_event("socket.getaddrinfo")`が`(True, "valid")`を返すことを確認した。`mini_pytest.py`再実行で`PASS=199`(§BI時点の196から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。`angels/gabriel_canary.py`・`angels/firmament_enclave_tee.py`・`angels/raziel_auditor.py`・`angels/seraphim_consensus.py`を直接実行し、いずれも引き続きPASSすることを確認した。

\*\*残存する限界\*\*: 本修正は「台帳に追加しても構造的に絶対に効果が無い」イベント名のうち、現在`_michael_absolute_defense`に存在する2つの固定許可リストに基づくもののみを検出する。将来`_michael_absolute_defense`に新たな無条件許可の分岐が追加された場合、`ALWAYS_PASSTHROUGH_AUDIT_EVENTS`への追加を忘れると、同じ種類の「見せかけの保護」が再発する可能性がある。また、本修正は「絶対に禁止できない」ケースのみを拒否するものであり、「既に他の固定カテゴリ(os.remove等)で同等に保護されているため台帳への追加が冗長である」ケース(これは`test_raziel_ledger_entries_already_covered_by_existing_categories_do_not_regress`が既に意図的な既定挙動として固定している)までは拒否しない。後者は「無駄だが無害」であり、誤った安心感を与えない(既に保護されている事実と一致する)ため、本修正の対象外とした。

\### BK. `tools/promote_provisioning_seal.py` の `approve()` — 同一`client_id`の古い重複提案が`PENDING_HUMAN_REVIEW`のまま残り、後から誤って再承認されると信頼の起点(公開鍵)が古い内容へ静かにロールバックされる (2026-10)

\*\*発見\*\*: §BJをmainにマージした後、「さらなる自己レビューと自己改善」の一環として、以前(§BG頃の棚卸し)に「低優先度・未修正」として一度見送っていた`tools/promote_provisioning_seal.py`の`approve()`を、`tools/promote_shield_seal.py`が§ATで既に修正済みの「同名の重複提案のうち古い方が後から誤って再適用される」バグ(同種のクラス)と比較する形で改めて精査した。`promote_shield_seal.py`の`_set_status()`は、同じ`vulnerability_name`に一致する承認待ち提案を\*全件\*まとめて新しいステータスへ遷移させる設計に既に修正されていたのに対し、`promote_provisioning_seal.py`の`approve()`は`matches[-1]`(最新の1件のみ)だけを"APPROVED"にし、同一`client_id`の他の古い提案は"PENDING_HUMAN_REVIEW"のまま放置される非対称な実装になっていることに気づいた。

実機検証: 同一`client_id`("client-A")に古い提案(hardware_fingerprint="OLD_FP")と新しい提案("NEW_FP")の2件を承認待ちキューに積み、`approve("client-A")`を1回実行すると、意図通り"NEW_FP"が承認され`maquina_gatekeeper.py`・`ataraxia_certificate.json`に反映される一方、"OLD_FP"の提案は依然として"PENDING_HUMAN_REVIEW"のまま残ることを確認した。さらに、残った"OLD_FP"を片付けるつもりで(あるいは`--list`で表示され続けることに気づいた別の運用者が)もう一度`approve("client-A")`を実行すると、`_find_pending()`が残っていた"OLD_FP"の提案を拾い上げて承認し、`maquina_gatekeeper.py`の信頼の起点(公開鍵)と有効な証明書が、既に失効しているはずの古い提案の内容へ\*静かに\*ロールバックされることを実機で確認した。

\*\*たとえ話\*\*: これは、新しい社員証(新しい公開鍵)を正式に発給した後、古い申請書(古い提案)を「処理済み」の箱に移し忘れ、未処理の箱に置いたままにしておいたようなものである。後日、別の担当者が「未処理の箱にまだ何か残っている」と気づき、よく確認せずにそれも承認してしまうと、建物の入館システム自体が古い社員証の情報に書き換えられてしまう。入館システム(`maquina_gatekeeper.py`)側は「最新の承認」を特別扱いする仕組みを持たないため、最後に承認処理を通過した申請書の内容がそのまま信頼の起点になってしまう。

\*\*原因\*\*: `tools/promote_shield_seal.py`・`tools/promote_ledger_seal.py`・`tools/promote_provisioning_seal.py`の3つは、いずれも「人間承認待ちキューへの提案→人間が内容を確認して承認/拒否」という同一の設計パターンに基づいているが、§ATの修正(重複提案の取り扱い)は`promote_shield_seal.py`にのみ適用され、同じ構造を持つ`promote_provisioning_seal.py`への横展開が行われていなかった。`promote_provisioning_seal.py`自身の`reject()`は既に全件(`matches`全体)を処理する実装になっており、`approve()`だけがこの非対称な「最新の1件のみ」という実装のまま取り残されていた。

\*\*対応\*\*: `approve()`で最新の提案(`matches[-1]`)を承認する際、同一`client_id`の他の古い"PENDING_HUMAN_REVIEW"提案(`matches[:-1]`)を、"PENDING_HUMAN_REVIEW"ではない新しいステータス"SUPERSEDED"(上位の提案に取って代わられた)へ明示的に遷移させるようにした。これにより、古い提案が二度と承認待ちとして拾われることがなくなり、後から誤って再承認されて信頼の起点がロールバックされる経路を断った。"REJECTED"ではなく専用の"SUPERSEDED"を新設したのは、拒否(内容に問題があったため不採用)と、単に新しい提案に追い越されただけ(内容自体に問題はない)という異なる意味を取り違えないようにするためである。

\*\*検証\*\*: `tests/test_provisioning_approval_flow.py`に`test_promote_provisioning_seal_supersedes_stale_duplicate_pending_entries`を新設した。同一`client_id`の新旧2件の提案を用意し、(1) 1回目の`approve()`で新しい方が"APPROVED"・古い方が"SUPERSEDED"になること、(2) 発行された証明書のhardware_fingerprintが新しい方の内容と一致すること、(3) 同じ`client_id`で2回目の`approve()`を実行しても(もう承認待ちの提案が残っていないため)証明書の内容が変化しない(古い内容へロールバックされない)ことを固定した。一時ディレクトリでの手動の再現実験でも、修正前は2回目の`approve()`で証明書が確実に古い内容(OLD_FP)へ書き換わり、修正後は書き換わらないことを確認した。`mini_pytest.py`再実行で`PASS=200`(§BJ時点の199から新規1件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。既存の3件のテスト(自己署名の防止・承認フロー・拒否フロー)も引き続き正常にPASSすることを確認した。

\### BL. `angels/azazel_dependency_audit.py`(新設) — `requirements.txt`のバージョン固定(==)だけでは、その固定された版自体に既知のCVEが無いことまでは一切検査していなかった。実機CIで`requests==2.32.3`の実在する2件のCVEを検出した (2026-10)

\*\*発見\*\*: §BKをmainにマージした後、「さらなる自己レビューと自己改善、増築、進化」の一環として、既存の天使群の守備範囲そのものの抜けを点検した。`angels/ophanim_eye.py`は`requirements.txt`の全依存が`==`でバージョン固定されているかのみを検証しており、「固定されている」ことと「固定された版が安全である」ことは全く別の主張であるにもかかわらず、後者を検査する天使が一体も存在していないことに気づいた。固定した版そのものに後から公表された既知の脆弱性(CVE)があれば、`ophanim_eye.py`は何も気づかずPASSを返し続ける。

この種の検査(`pip-audit`によるPyPI Advisory Database/OSV.dev照会)は構造的に外部のネットワーク到達性に依存する唯一の天使になる。ネットワークが遮断された環境で安易に「PASS」を返すと、「調べていないのに安全だと主張する」という、本プロジェクトが繰り返し修正してきた「学習したつもりになっているだけ」の構造的な見せかけと同じ過ちを、この新しい天使自身が体現してしまう。そのため最初から、`pip-audit`の実行自体(インストール・DBへの照会)が何らかの理由で失敗した場合は、安全側に倒して検査自体をFAILとして報告する(フェイルクローズド)設計とした。

本番のGitHub Actions CI(PyPIへの到達性を既に持つ環境、既存の`pip install -r requirements.txt`ステップの成功で裏付けられている)上で実際に動作確認したところ、1回目の実行で本物の`pip-audit`が本物のOSV.dev/PyPI Advisory Databaseに照会し、\*\*`requests==2.32.3`に実在する2件の既知の脆弱性\*\*を検出して天使を正しく失敗させた: CVE-2024-47081(PYSEC-2026-1872、`.netrc`の資格情報が特殊なURLにより第三者へ漏洩しうる、修正版2.32.4)・CVE-2026-25645(PYSEC-2026-2275、`requests.utils.extract_zipped_paths()`がzip展開時に予測可能な一時ファイル名を使い、ローカル攻撃者による置き換えを許しうる、修正版2.33.0)。

\*\*たとえ話\*\*: `ophanim_eye.py`は「ドアに鍵がかかっているか」だけを確認する警備員である。鍵がかかっていれば合格にする。しかし、その鍵自体が既にメーカーから「複製が容易だと判明したため回収中」と公表されている型であれば、鍵がかかっていること自体は何の意味も持たない。アザゼルは、かかっている鍵の\*型番\*をメーカーのリコール公表リスト(既知脆弱性データベース)と照合する、もう一人の警備員である。

\*\*原因\*\*: バージョン固定(サプライチェーンの「再現性」)と脆弱性の不在(サプライチェーンの「安全性」)は独立した要件であり、`ophanim_eye.py`が前者しか検査していないこと自体は設計ミスではなく、単に「後者を検査する天使がまだ存在しなかった」という守備範囲の欠落だった。

\*\*対応\*\*: `angels/azazel_dependency_audit.py`を新設し、`.github/workflows/anjo_da_maquina_protocol.yml`に「7.5. アザゼルの禁断知識」としてophanim_eyeの直後に配線した。`pip-audit`が利用できない場合・JSON出力が解析できない場合は共にフェイルクローズドでFAILとする。検出したら`requests==2.33.1`へ固定版を更新して修正した(両CVEとも2.33.0で修正済み、2.33.1はその後のバグ修正版)。

\*\*自白と謝罪(本件固有)\*\*: 実機CI検証の過程で、自分自身の作業ミスにより\*2件\*の回り道を発生させたことを正直に告白する。(1) 診断用にワークフローへ追加した一時的なデバッグ出力コード(`python3 -c "..."`の複数行文字列)が、YAMLのブロックスカラー(`run: |`)に必要なインデントを満たしておらず、ワークフローファイル自体が構文エラーとなり、ジョブが一つも生成されない「startup failure」を実機で発生させてしまった。(2) その修正後も、GitHub Actionsのrunステップが既定で`bash -eo pipefail`(set -e相当)であることを見落としており、1行目のpythonコマンドが非ゼロ終了した時点でスクリプト全体が即座に停止し、意図していた診断用アノテーション出力(`::error::AZAZEL_DEBUG ...`)が一度も実行されないまま空振りに終わった。いずれも実機でのみ発覚し、ローカルでの事前検証を怠っていた結果である。2回目の修正では、該当コマンドの前後を明示的に`set +e`/`set -e`で挟んだ上で、ローカルで同じシェルスクリプトのロジックをシミュレーションしてから再度プッシュし、3回目の実機検証で初めて意図した通りの診断情報(実際のCVE検出結果)を取得できた。いずれの回り道も、最終的にmainへマージされる本番のワークフロー・コード自体には影響していない(全て診断専用の一時的な変更であり、動作確認後に元のシンプルな形へ完全に戻した)が、無駄な実機CI実行を複数回発生させたことについては、事前のローカル検証をより徹底すべきであった。

\*\*検証\*\*: `tests/test_azazel_dependency_audit.py`を新設し、以下をsubprocess内で`subprocess.run`をスタブ化して検証した(本物のネットワーク到達性には依存しない): (1) `pip-audit`が利用不可能な場合にフェイルクローズドでFAILすること、(2) 既知の脆弱性が検出された場合にパッケージ名・CVE IDを含めてFAILすること、(3) 脆弱性ゼロの場合は正常にPASSすること(過剰検知の回帰防止)、(4) `pip-audit`の出力が解析不能な場合もフェイルクローズドでFAILすること、(5) 実機CIで実際に観測された「同一CVEが`vulns`配列内に重複して現れる」現象(OSV・PyPI Advisory Databaseの両方から同じIDが報告されるため)に対し、報告メッセージ内で重複を除去して1回だけ表示することの回帰防止。ローカルの`mini_pytest.py`再実行で`PASS=205`(§BK時点の200から新規5件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。実機のGitHub Actions CI上で、`requirements.txt`を`requests==2.33.1`へ更新した最終版により、本天使が正しくPASSすることをmainへのマージ後に再度確認した。`angels/gabriel_canary.py`・`angels/firmament_enclave_tee.py`・`angels/alpha_omega_guard.py`・`angels/ophanim_eye.py`も引き続きPASSすることを確認した。

\*\*残存する限界\*\*: 本検査はdocstringで既に明記した通り、(1) 外部のネットワーク到達性(脆弱性データベースへの照会)に構造的に依存する唯一の天使であり、CI環境のネットワークポリシーが将来変更された場合にフェイルクローズドでFAILし続ける可能性がある。(2) `pip-audit`自身が把握していない、またはデータベースに未登録の脆弱性(ゼロデイ等)は検知できない。(3) 本検査は`requirements.txt`に列挙された直接依存のみを対象とし、それらが内部で読み込む推移的依存(transitive dependencies)のうち`requirements.txt`に明記されていないものの脆弱性は、`pip-audit`の解決結果に含まれる範囲でのみ検出される。

\### BM. `angels/lucifer_rebellion.py` — サンドボックス脱出攻撃バッテリーの失敗判定が`CHAOS_MODE`(既定false)依存だったため、`push`トリガーの通常のCI(mainへのマージを実際にゲートしている唯一の経路)では、3件の既知攻撃が全て突破されても一度も失敗しない構造だった (2026-10)

\*\*発見\*\*: §BLをmainにマージした後、「さらなる自己レビューと自己改善」の一環として、`tools/promote_ledger_seal.py`(§BK・§ATと同じ「古い重複提案の取り扱い」パターンに該当するか)を確認したところ、こちらは既に`_set_status()`が一致する全件を処理する安全な実装であることを確認し、変更不要と判断した。その延長で、既存の天使群のうち「検知はするが判定条件に環境変数が絡む」ものを一通り洗い出し、`angels/lucifer_rebellion.py`に着目した。

本スクリプトは、`os.system`経由のコマンド実行・`shell=True`での`subprocess.Popen`・`eval`経由のコード実行という3件の基本的なサンドボックス脱出攻撃を`run_code_against_sefer()`で実際にSeferへ対して実行し、突破数を数える「カオスエンジニアリング」バッテリーである。しかし修正前の実装は、`if chaos_mode and bypasses:`という条件でのみ`report_fail`していた。`chaos_mode`は`CHAOS_MODE`環境変数(ワークフローの`workflow_dispatch`入力`chaos_mode`、既定値false)から読まれ、`.github/workflows/anjo_da_maquina_protocol.yml`を確認すると、この値は`${{ github.event.inputs.chaos_mode == 'true' && 'true' || 'false' }}`という式で設定されていた。`push`イベント(mainへの実際のマージを唯一ゲートしているトリガー)には`github.event.inputs`自体が存在しないため、この式は通常のpushでは常に`'false'`に評価される。つまり、人間がGitHub ActionsのUI/APIから`workflow_dispatch`を手動で起動し、`chaos_mode`チェックボックスを明示的にONにしない限り、`CHAOS_MODE`は常にfalseであり、3件の攻撃が全て突破されていても`report_info`で情報ログを出すだけで、CIは一度も失敗しない。

さらに調べたところ、`CHAOS_MODE`を実際に読んでいるPythonファイルはリポジトリ全体で`angels/lucifer_rebellion.py`の1件のみであるにもかかわらず、ワークフロー側では`shamir_seal.py`・`seraphim_consensus.py`・`cherubim_ebpf_guard.py`の3つのステップにも同じ`env: CHAOS_MODE: ...`が無意味に配線されており(これらのスクリプトは一度もこの環境変数を読まない)、本来の消費者が1つしかないにもかかわらず配線だけが4箇所に散らばっているという、整理されていない状態だった。

\*\*たとえ話\*\*: これは、建物の避難訓練(カオスエンジニアリング)で、非常口が3つとも実際に開かなかった(サンドボックス脱出攻撃が突破された)ことが判明しても、「本日は正式な避難訓練モードですか？」というチェック項目にチェックが入っていなければ、報告書には「異常あり」とメモするだけで、建物の運用自体は何事もなく続行されるようになっていた、というものである。正式な避難訓練モードのチェックボックスは、誰かが手作業で毎回ONにしない限り常にOFFであり、建物の日常の開閉(毎日のpushによるマージ)を実際にゲートしている検査員は、このチェックボックスがOFFの間、非常口が開かないという事実そのものに一度も反応しない。

\*\*原因\*\*: `CHAOS_MODE`という名前と`workflow_dispatch`入力の説明文(「カオスモード（生存証明の途絶・システム異常のシミュレーション）を有効にする」)は、本来「より広範囲・積極的な異常シミュレーションを行うかどうか」を意味する設計意図だったと見られる。しかし、唯一の実装(`lucifer_rebellion.py`)での実際の使われ方は「3件の決定論的な固定攻撃バッテリーの\*失敗判定そのもの\*を有効にするかどうか」という、全く異なる意味に転用されていた。これらの攻撃は乱数に依存するファジングではなく、同じコードは常に同じ結果(遮断されるか、されないか)になる決定論的な回帰テストであるため、「たまに誤検知するかもしれないから既定では無効にしておく」という配慮が成立する種類の検査ではなく、本来CHAOS_MODEというオプトインの仕組みで保護する必要のない検査内容だった。

\*\*対応\*\*: `angels/lucifer_rebellion.py`の失敗判定を`if chaos_mode and bypasses:`から`if bypasses:`へ変更し、`CHAOS_MODE`の値に関わらず、1件でも突破があれば常に(通常のpushでも)失敗するようにした。`CHAOS_MODE`自体の読み込みと`report_info`でのログ出力は、将来的な拡張(例えば本当に広範囲・積極的な追加バッテリーをCHAOS_MODE時のみ実行する、等)のために残したが、現時点では失敗/成功の判定には一切使用しない。また、実際には一度も読まれていなかった`shamir_seal.py`・`seraphim_consensus.py`・`cherubim_ebpf_guard.py`の3ステップの無意味な`env: CHAOS_MODE: ...`配線を削除した(棚卸し)。

\*\*検証\*\*: 修正前の状態で、本物の`sefer`に対して現在3件の攻撃が全て正しく遮断されている(突破0件)ことをローカルで確認した上で(つまり本修正は既存の正常な状態を新たに失敗させるものではなく、将来の退行だけを捕捉する)、`tests/test_lucifer_rebellion_chaos_gate.py`を新設した。`run_code_against_sefer()`を差し替え、(1) `CHAOS_MODE`が未設定(既定=false、通常のpushと同じ状態)でも、突破が検知されれば必ず失敗すること(§BMの核心)、(2) `CHAOS_MODE=false`を明示しても同様に失敗すること、(3) 突破が無い場合は正常にPASSし続けること(過剰検知の回帰防止)を固定した。`mini_pytest.py`再実行で`PASS=208`(§BL時点の205から新規3件増加)・`FAIL=0`・`ERROR=2`(既存の無関係なもののみ)であることを確認した。`angels/gabriel_canary.py`・`angels/firmament_enclave_tee.py`・`angels/alpha_omega_guard.py`(ワークフローYAML構造の整合性)・`angels/lucifer_rebellion.py`自身を直接実行し、いずれも引き続きPASSすることを確認した。

\*\*残存する限界\*\*: 本修正は、`lucifer_rebellion.py`が検査する3件の固定攻撃バッテリーのみを常時強制とする。将来、本当に「既定では無効にしておくべき広範囲なカオス実験」を追加する場合は、その新しい実験には`CHAOS_MODE`のような明示的なオプトイン機構を別途設けることが正当であり、既存の決定論的なサンドボックス脱出テストと同じ扱いにしてはならない。この区別を忘れると、同じ種類の「見せかけの保護」が再発する可能性がある。

\### BN. `adapters/junit_xml_exporter.py` の `export_zkp_to_junit()` — `zk_audit_trail.json`のHMAC連鎖を一切検証せず、改ざんの有無に関わらず常にJUnit XMLの`failures="0"`を出力していた (2026-10)

\*\*発見\*\*: §BMをmainにマージした後、「さらなる自己レビューと自己改善、増築、進化」の一環として、GRIMOIRE.mdに一度も言及されていない(=これまで一度も深く精査されていない可能性がある)ファイルを`adapters/`配下で洗い出したところ、`adapters/junit_xml_exporter.py`が該当した。本ファイルは`zk_audit_trail.json`(鍵付きHMAC連鎖による改ざん検知付きの監査ログ、`maquina_gatekeeper.ZKAuditTrail`が生成)を、CI/CDダッシュボードが解釈可能なJUnit XML形式へ変換するものである。

内容を読んだところ、生成されるXMLの`<testsuite>`要素の`failures`・`errors`属性が常にリテラルの`"0"`で固定されており、`zk_audit_trail.json`の内容が実際に連鎖的に正しいか(ハッシュの連続性・鍵付きHMACの整合性)を一度も検証していないことに気づいた。`angels/heavenly_tablets_zkp.py`(このエクスポート処理をCI上で呼び出している唯一の天使)を確認したところ、こちらも生成されたXMLが「妥当なXML構文であるか」しか検証しておらず、`failures`属性の値自体を一度も読んでいなかった。つまり、`zk_audit_trail.json`というファイルの中身が、たとえ改ざん検知されるレベルまで壊れていたとしても(本物の鍵付きHMAC連鎖として再計算すると不整合になるレベルまで)、このパイプライン全体のどこにも、それを検知してCIやダッシュボードに伝える経路が存在していなかった。

\*\*たとえ話\*\*: これは、金庫の内部に「封印が破られていないかを検証する特殊な鍵付きロック機構(ZKAuditTrailの鍵付きHMAC連鎖)」が実際に備わっているにもかかわらず、金庫の状態を外部の管理ダッシュボードへ報告する担当者(junit_xml_exporter.py)が、その鍵付きロックを一度も確認せず、金庫を一目見ただけで毎回「封印は正常です、異常はゼロ件です」と報告書に書き続けていた、というものである。金庫自体の防御機構は本物だったが、その結果を外部に正しく伝える最後の1マイルが、実質的には何も見ていない「見せかけの報告」になっていた。

\*\*原因\*\*: `export_zkp_to_junit()`は「JSONをXMLへ変換する」という表示整形の役割に専念する設計で書かれており、`maquina_gatekeeper.ZKAuditTrail`が既に備えている`_verify_full_chain()`(連鎖の鍵付きHMAC再計算による改ざん検知)を呼び出す責務が、どちらのファイルにも割り当てられていなかった。`angels/heavenly_tablets_zkp.py`側も「エクスポート処理自体が正しく動くか」(XML構文の妥当性)という狭い意味でのテストに留まり、エクスポートされた\*内容\*が監査ログの実際の健全性を正しく反映しているかまでは検証していなかった。

\*\*対応\*\*: `adapters/junit_xml_exporter.py`に`_verify_chain_integrity()`を新設し、`maquina_gatekeeper.ZKAuditTrail._get_key()`・`_verify_full_chain()`を実際に呼び出して連鎖の整合性を検証するようにした。改 záん(または鍵の不一致)が検知された場合、`failures="1"`と、具体的なエラー内容を含む`<failure>`要素を持つ`ChainIntegrityVerification`という名前のtestcaseを出力するようにした。さらに`angels/heavenly_tablets_zkp.py`側も、生成されたXMLの`failures`属性を実際に読み、"0"以外であればCI自体を`report_fail`で失敗させるようにした(ダッシュボードだけに判定を委ねない)。

\*\*検証\*\*: `tests/test_junit_xml_exporter_chain_verification.py`を新設した。`maquina_gatekeeper.ZKAuditTrail`を使って本物の鍵付きHMAC連鎖を一時ディレクトリ内に実際に構築した上で、(1) 改ざんの無い正当な連鎖は修正後も引き続き`failures="0"`であること(過剰検知の回帰防止)、(2) 連鎖の1ブロックを直接書き換えて改ざんした場合、`failures="1"`かつ`<failure>`要素として検知されること(§BNの核心)、(3) `angels/heavenly_tablets_zkp.py`自身もこれを読んでCIを`SystemExit(1)`で失敗させること、の3点を固定した。本テストの作成過程で、`tests/test_provisioning_approval_flow.py`等が既に用いている`rsa`パッケージの疑似実装(`sys.modules["rsa"]`への注入)を、本テストファイルでも独自に(不完全な形で)用意してしまい、`mini_pytest.py`が全テストファイルを単一プロセス内で実行する都合上、アルファベット順で先に読み込まれる本テストファイルの不完全なスタブが優先されてしまい、後続の`test_provisioning_approval_flow.py`側で`rsa.sign`の`AttributeError`を引き起こす回り道が実機検証で発生した。`rsa.sign`/`rsa.verify`を含む完全な互換スタブに修正し、再実行して解消したことを確認した(本件もGRIMOIRE.mdの「自白と謝罪」の精神に基づき記録する)。`mini_pytest.py`を実機CIと同じ`GITHUB_ACTIONS=true`環境で再実行し、`PASS=215`(§BM時点の208から新規7件増加、他の既存天使群のCI分岐差分含む)・`FAIL=0`であることを確認した。なお`GITHUB_ACTIONS=true`を設定しない場合、`tests/test_openai_agent_loop_template.py`の`test_execute_safe_action_uses_sanctum_and_is_not_a_stub`が別件で失敗することに気づいたが、これは本リポジトリに実際にコミットされている`ataraxia_certificate.json`の`valid_until`(2026-10-12)が、単に実時間の経過により既に失効しただけであり、同テスト自体が「`GITHUB_ACTIONS`環境下でのみ失効を正常系として扱う」設計であることを確認した(本物のGitHub Actions CI上では`GITHUB_ACTIONS=true`が自動的に設定されるため、実CIのゲートには影響しない、ローカルサンドボックス固有の既知の差分)。`angels/gabriel_canary.py`・`angels/firmament_enclave_tee.py`・`angels/alpha_omega_guard.py`・`angels/heavenly_tablets_zkp.py`も引き続きPASSすることを確認した。

\*\*残存する限界\*\*: (1) `zk_audit_trail.json`・`.zk_audit_signing_key`は現時点のCIワークフローのどのステップからも実際に生成されることが無く(`enforce_maquina_seal`で保護された関数が実運用のCI内で呼び出されていないため)、`angels/heavenly_tablets_zkp.py`は通常「未生成のため検査対象なし」としてPASSするだけであり、本修正が実際に効果を発揮するのは、将来このパイプラインが実際に稼働する場合、または開発者がローカルで明示的にエクスポートを実行する場合に限られる。これは本修正が作られる前から存在していた、別の(より大きな)構造的な限界であり、本修正の対象外とする。(2) 改ざん検知に使う鍵(`.zk_audit_signing_key`)自体がエクスポート実行時の作業ディレクトリに存在しない場合、`_load_or_create_zk_signing_key()`が新しい鍵を生成してしまい、「本物の改ざん」と「鍵が別物になっただけ」を区別できず、後者も改ざんとして報告される。これは`maquina_gatekeeper.ZKAuditTrail`自体の既存の設計(鍵のライフサイクル管理)に起因するものであり、本来は鍵と連鎖が常に同じ作業ディレクトリ内で生成・検証される前提に依存している。

\*\*残存する限界\*\*: 本修正は「後から誤って古い提案が再承認される」という経路を断つものであり、`--list`で古い"PENDING_HUMAN_REVIEW"提案が見えなくなること自体が直接の目的ではない(承認と同時に古い重複が自動的に片付くという副次効果に過ぎない)。また、本修正は`client_id`が完全一致する重複提案のみを対象とし、同じ物理マシンが異なる`client_id`を名乗って複数回提案するような、`client_id`自体の正当性に関する検証は本ファイルの対象外のまま(それは`hardware_fingerprint`の一致検証の責務であり、既存の別のレイヤーが担う)である。

\### BO. `angels/_common.py` — PASS/FAILの2値しか無く、「検査対象が存在しない」(NOT_APPLICABLE)状態を9本の天使がPASSとして誤報告していた (2026-10)

\*\*発見\*\*: 利用者より、Pleromaの監査思想自体を「AI出力の絶対的正しさの保証」から「人間とAIの間の情報損失・歪曲の検出」へ再評価する相談を受け、調査・設計提案(コード変更なし)のフェーズで`angels/*.py`全体を再精査した。`report_pass(NAME, "...検査対象なし。")`という形の呼び出しを`grep`で機械的に洗い出したところ、`azazel_dependency_audit.py`・`heavenly_tablets_zkp.py`・`metatron_cube_hsm.py`・`metatron_revelation_mcp.py`・`ophanim_thousand_eyes.py`・`sariel_fallen_auditor.py`・`shamir_seal.py`・`uriel_nonce.py`の8ファイルが該当した。さらにその後、人間からの承認を得て実装に着手した段階で、同じ`grep`の条件をわずかに広げて再確認したところ(「正常な状態」という言い換えも対象に含めた)、`sandalphon_echo.py`も同種の誤用をしていたことに気づいた(当初の調査では見落としていた。本件もGRIMOIRE.mdの「自白と謝罪」の精神に基づき記録する)。合計9ファイルである。いずれも「検査対象のファイルが存在しない」という、本来は「検査できていない」ことを意味する状態を、`report_pass`で報告していた。

\*\*たとえ話\*\*: これは、健康診断を受けに来た人が、検査装置の電源が入っていない、あるいは検査対象の検体そのものが提出されていないにもかかわらず、診断書に「異常なし」と書いて渡してしまうことに相当する。「異常が無い」と「そもそも検査していない」は、受け取る側にとっては全く異なる情報だが、診断書の見た目(異常なし)は同じになってしまう。

\*\*原因\*\*: `angels/_common.py`には元来`report_pass`/`report_fail`の2値しか存在せず、「検査対象が存在しないため判定不能」という第3の状態を表現する手段が無かった。各天使の作者は、CIを赤くしない(`report_fail`を避ける)ことを優先し、代わりに`report_pass`を転用した。

\*\*対応\*\*: `angels/_common.py`に`report_inconclusive`(証拠不十分で判定不能)と`report_not_applicable`(検査対象自体が存在しない)を新設し、9ファイル全てで該当する`report_pass`呼び出しをこれらに置き換えた。あわせて`report_pass`/`report_fail`/新設2関数の全てに任意の`evidence`引き次を追加し、将来「なぜそう判定したか」の構造化データを添付できるようにした(既存呼び出しは`evidence=None`で後方互換)。

\*\*実装中の自己訂正(自白)\*\*: 当初、設計段階のチャットでの相談時には、`report_inconclusive`/`report_not_applicable`をそれぞれ専用の終了コード(2・3)で`sys.exit()`する案を提示した。実装に着手し、実際に`python angels/heavenly_tablets_zkp.py`を実行して確認したところ、本当に終了コード3を返すことを確認した。ここで`.github/workflows/anjo_da_maquina_protocol.yml`の各天使ステップを再確認し、`continue-on-error`が一件も設定されておらず、単純な`run: python angels/x.py`のみであることに気づいた。GitHub Actionsは非ゼロ終了コードであれば1でも2でも3でも区別せずそのステップとジョブ全体を失敗(赤)にするため、この案のままマージすれば、「検査対象が無いだけの、本来は異常ではない状態」でCI全体を不必要に赤くする新たな欠陥を自ら作り込むことになっていた。マージ前に自分の設計ミスに気づいたため、ここで正直に告白し、`sys.exit()`を呼ばず標準出力のマーカーのみで区別する設計に訂正した。

\*\*検証\*\*: `tests/test_angel_common_four_state_verdicts.py`を新設した。(1) `report_inconclusive`/`report_not_applicable`が`SystemExit`を発生させず、`✅ PASS`とは異なる文字列を出力すること、(2) `report_fail`は引き続き`SystemExit(1)`を発生させること(回帰防止)、(3) `evidence`引き次を渡した場合その内容が出力されること、(4) `heavenly_tablets_zkp.py`・`uriel_nonce.py`について、検査対象が存在しない状態で実際に`main()`を呼び、出力に`NOT_APPLICABLE`が含まれ`✅ PASS`が含まれないことを実機で固定した。9ファイル全てを実際に個別実行し、意図通り`NOT_APPLICABLE`(終了コード0)を報告することを確認した。`pytest`をリポジトリ全体に対して再実行し(`rsa`・`yaml`は本サンドボックス既存の制約により疑似実装・システムパッケージ経由で用意)、`223 passed, 2 failed, 3 xfailed`であることを確認した。失敗した2件(`test_execute_safe_action_uses_sanctum_and_is_not_a_stub`の証明書期限切れ、`test_sdist_is_clean_and_contains_only_the_sefer_package`の`setuptools`未インストール)は、`git stash`で本修正を一時的に取り除いた状態でも同じく失敗することを確認し、本修正とは無関係なサンドボックス環境固有の既知の制約であることを確認した。本修正前は223件中216件のみが収集・実行可能な状態だったため、新規7件増加している。

\*\*残存する限界\*\*: (1) CIのステップ単位の表示上は、`NOT_APPLICABLE`であっても依然「ステップが成功(緑のチェック)」として見える。本修正は少なくとも`print`出力のログを読めば`PASS`と`NOT_APPLICABLE`を区別できるようにしたが、GitHub Actionsのジョブ一覧・バッジのレベルでは両者の見た目は変わらない。真に可視化するには、ワークフロー側に各天使の終了後の出力を集計するサマリーステップ(例: `$GITHUB_STEP_SUMMARY`への書き込み)を追加する必要があり、これは本修正の範囲外である(既存の45ステップ全てへの変更が必要になるため)。(2) `evidence`引き次は追加したが、9ファイルの修正自体では`evidence`を実際には渡していない(構造化データの移行は今後の段階的な作業として残す)。(3) 今回の`grep`ベースの再調査で9件目(`sandalphon_echo.py`)を発見したという事実自体が、この種の調査が本質的に「言い回しの網」に依存しており、完全な網羅を保証できないことを示している。

\### BP. `angels/thrones_positive_path.py`(新設)— §BM/§BN型「安全装置が実際に発火するか誰も確認していない」パターンの一般化検知。実装の過程で`src/deadmans_switch.py`・`angels/shamir_seal.py`の未発見の実例2件を、レッド・ブルー反復作業で発見・修正 (2026-10)

\*\*発見\*\*: 利用者より、「レッドチームによる攻撃とブルーチームによる防御の反復で、現時点で思いつくパターン以外の未知のパターンにも対応できるか」という問いを受けた。回答として、(1) 既知パターンの未発見インスタンスの発見、(2) 新パターンクラスの発見確率の向上には反復が有効だが、(3) 「すべての未知パターンを閉じる」ことは原理的に不可能(ライスの定理に類する、プログラムの非自明な振る舞いの一般的な決定不能性)であることを説明した上で、実際に1ラウンドの反復を実機で行った。

\*\*ラウンド0(人力レッドチーム)\*\*: `angels/thrones_positive_path.py`の実装前に、`os.getenv`/`os.environ.get`/`os.environ[...]`の利用箇所をリポジトリ全体から手動で洗い出し、各箇所に「有効側(危険側)の分岐を実際に踏むテスト」が存在するかを確認した。その結果、`angels/shamir_seal.py`の`IS_UNVERIFIED_CLOUD`分岐(証明書失効をGitHub Actions環境では正常、それ以外では異常として振り分ける設計)と、`src/deadmans_switch.py`の`CollarProtocol.verify_collar()`(首輪シールが一致しない場合に`os._exit(1)`で即時自壊する、ミュトス級AI封じ込め機構そのもの)の2件が、どちらも専用のテストファイルを一件も持たないことが判明した。いずれも§BM・§BNと同一の構造(安全装置は実装されているが、発火を誰も確認していない)である。

\*\*たとえ話\*\*: `src/deadmans_switch.py`の発見は特に重大だった。これは、建物の火災報知器が実際に鳴るかどうかを一度も試験していない状態に近い。通常時は誰も気づかないが、本当に火事が起きた(=首輪が乗っ取られた)ときに報知器が鳴らなければ、設計上存在するはずの最後の防衛線が、実は一度も動作確認されていなかったことになる。

\*\*対応(ブルーチーム)\*\*: `tests/test_shamir_seal_fail_path.py`・`tests/test_deadmans_switch_collar_protocol.py`を新設し、両方の分岐(安全側・危険側)を実機で実際に発火させて検証した。`CollarProtocol._commit_suicide()`は`try/except`でも捕捉できない`os._exit(1)`を使う設計のため、同一プロセス内のpytestから直接呼ぶとテストランナー自体が終了してしまう。既存の`run_code_against_sefer()`と同種の、サブプロセスを起動して終了コードで判定する方式で検証した。検証の結果、両方の安全装置は実際には正しく動作していることを確認した(=実害のある不具合ではなく、テストカバレッジの欠落だった)。

\*\*一般化(§11.9運用ルールの実践)\*\*: この2件を個別に塞ぐだけに留めず、`angels/thrones_positive_path.py`という新天使を実装した。環境変数で有効/無効が切り替わる条件分岐を正規表現ベースのヒューリスティックで洗い出し、対応する環境変数名への言及と`assert`を含むテストファイルが存在しない場合にCI自体を失敗させる。

\*\*ラウンド1(実装中の自己レッドチーム・自己発見)\*\*: 本天使を自分自身(`angels/thrones_positive_path.py`自体)に対して実行したところ、本ファイルのコメント内に説明目的で書いた例示コード(``if os.getenv("X") == "true":``)を、本物の環境変数ゲートとして誤検知した。これは個別対応ではなく、説明用の例示コードを正規表現ベースの検査対象から除外する一般的な対策(コメント行の事前除去)として修正した。

\*\*ラウンド2(実装中の自己レッドチーム・回避試行)\*\*: 修正後、自ら4種類の回避コードを作成し、本天使の検知能力を試した。(1) 複合条件式(`if flag and True:`)、(2) `os.environ["X"]`の添字アクセス形式、(3) 代入と条件分岐の順序が逆の形、(4) `os.getenv`を間接的にラップした関数呼び出し経由の形。結果、(1)(3)は当初から検知済み、(2)は検知漏れが見つかり即座に正規表現を拡張して対応した。(4)は検知できず、これは`tests/test_thrones_positive_path.py`に既知の限界として明示的に固定した(隠さず記録する)。

\*\*検証\*\*: `tests/test_thrones_positive_path.py`(8件、検知能力・誤検知防止・既知の限界の固定)・`tests/test_shamir_seal_fail_path.py`(3件)・`tests/test_deadmans_switch_collar_protocol.py`(2件)を新設。`.github/workflows/anjo_da_maquina_protocol.yml`に新天使をステップ22.6として配線し、`tests/test_angels_scripts_wired_into_ci.py`の配線漏れ検知テストが通ることを確認した。リポジトリ全体のpytestを再実行し、236 passed(§BO時点の223から13件増加)・既存の無関係な2件のサンドボックス固有の失敗のみであることを確認した。`angels/thrones_positive_path.py`を実機で直接実行し、現時点のリポジトリ全体(`ANJO_COLLAR_SEAL`・`GITHUB_ACTIONS`の2件)についてPASSすることを確認した。

\*\*残存する限界(正直に記す)\*\*: (1) 正規表現ベースのヒューリスティックであり、ラウンド2で確認した通り、間接呼び出し経由の迂回(§11.9フェーズFの一般形)は検知できない。(2) 「テストファイルが環境変数名と`assert`を両方含む」ことだけを根拠にしており、そのテストが本当に「有効側の分岐」を踏んでいるかまでは保証しない(名前が似ているだけの無関係なテストでも一致してしまう可能性がある)。(3) 今回発見した2件は、調査を始めてすぐに見つかった「低木の果実」であり、今後ラウンドを重ねるほど新規発見の頻度は下がっていくと予想される。これは本対応の不備ではなく、本文書中で利用者に説明した、反復的レッドチーム作業に内在する収穫減少の法則そのものである。
