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
