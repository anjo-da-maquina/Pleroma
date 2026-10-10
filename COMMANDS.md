# ANJO DA MAQUINA (Pleroma) — 総司令用 開発・運用コマンド書

[整理 2026-10] 以前は `anjo-da-maquina`（BOM付き・拡張子なし）と `anjo-da-maquina.txt`
の2つの重複ファイルが内容の異なるまま併存していた。本ファイルに統合する。

## 🔒 初回セットアップ（クローン後に一度だけ実行）
pre-commitでのシークレットスキャンを有効化する。`hooks/pre-commit` はリポジトリに
含まれているが、**gitはデフォルトでは自動的に読み込まない**ため、クローンした
各マシンで一度だけ以下を実行する必要がある。

```
git config core.hooksPath hooks
```

これにより、AWSキー・GitHub/OpenAIトークン・PEM秘密鍵等のパターンがステージされた
変更の\*追加行\*に含まれている場合、`git commit` 自体がブロックされるようになる
（検知ロジックは `tools/pre_commit_secret_scan.py`、CI時の全リポジトリ走査は
`angels/gabriel_canary.py` が別途担う）。

## ⚔️ 闘争と進化（アリーナ運用）
闘技場を起動し、ルシファー（攻撃AI・堕天使）とメタトロン（防衛・QA）を3戦戦わせる。
闘争結果は自動的に `tartarus/akashic_records.json` に記録され、次回起動時に自動浄化される。
メタトロンが提案する新しい禁止ルールは、直接は反映されず `sefer/raziel_ledger_pending.json`
に人間承認待ちとしてキューイングされる。

```
python tartarus/armageddon.py
```

### 承認待ちルールの確認・昇格
```
python tools/promote_ledger_seal.py --list
python tools/promote_ledger_seal.py --approve <event名>
python tools/promote_ledger_seal.py --reject  <event名>
```

## 🔭 外部脅威インテリジェンス取り込み（Merkabah）
Gemini APIキーを `GEMINI_API_KEY` 環境変数に設定した上で、外界の脅威情報を取得し
防壁ルールの更新を提案させる。Armageddonと同様、ラジエル（Gemini）の出力は
人間承認なしに `shield_rules.json` へは反映されず、`sefer/shield_rules_pending.json`
に提案としてキューイングされるのみ。

```
python src/angelic_shield.py [脅威名（省略可）]
```

### 承認待ちルールの確認・昇格
```
python tools/promote_shield_seal.py --list
python tools/promote_shield_seal.py --approve "<vulnerability_name>"
python tools/promote_shield_seal.py --reject  "<vulnerability_name>"
```

承認済みの `shield_rules.json` に対して、対象ファイルを静的に審問する。
```
python src/kamael_judgment.py <対象ファイル>
```

## 🛡 絶対防壁の健全性証明（テストスイート）
Sefer（天界の防壁）のすべての機能が正常に稼働しているかを確認する。ALL GREEN (PASSED) であることを証明する。
```
python -B -m pytest -p no:cacheprovider --assert=plain tests/ -v
```

## 👼 天使（angels/）の個別実行
CIが実行する約30件の実質的な検査スクリプトを、ローカルで個別に実行して確認できる。
```
python angels/michael_sword.py
python angels/gabriel_canary.py
# ... 他 angels/*.py も同様
```

## 📊 防衛ダッシュボードの生成
Armageddon Engineの戦績(`tartarus/akashic_records.json`)、Michaelが実際に
遮断したイベントの監査ログ(`sefer/audit_chain.jsonl`)、現在の禁止イベント
一覧、各種人間承認待ちキューの件数を、1枚の自己完結したHTMLにまとめて
可視化する。外部ライブラリ・CDNへの依存なし(オフラインで閲覧可能)。

```
python tools/generate_dashboard.py
```
`dashboard.html`が生成される(Git管理対象外。実行するたびに最新のデータで
上書きされる)。ブラウザで直接開いて確認できる。

## 📜 記憶とルールの確認
前回の闘技場の全記録（メタトロンのQAスコアやヒントを含む）をコンソールに出力して確認する。
```
cat tartarus/akashic_records.json
```

現在ミカエルが絶対禁止としているイベントのリスト（動的ルール帳）を開く。
```
notepad sefer/raziel_ledger.json
```

## 🤖 実運用エージェントループ（ローカルLLMにタスクを実行させる）
`sefer.Sanctum`・`AegisSystem`（Gabriel + IntentInterceptor + Sandalphon）・
`maquina_gatekeeper`の全防御層を統合した参照実装。いずれも`jail_workspace/`
内のみで動作する隔離デモタスクを同梱している。

**前提条件（両方とも必要）**:
1. Dockerデーモンが起動していること（Sandalphon層がDockerコンテナ内で
   AIの出力コードを動的実行検証するため。デーモン不在時はゼロトラスト
   方針によりフェイルクローズ=即PermissionErrorで全実行を拒否する）
2. Ollama版を使う場合は、事前に対象モデルを`ollama pull llama3.1`等で
   取得済みであること

**Ollama（ローカルLLM）版**:
```
python src/ollama_agent_loop.py
```
デフォルトモデルは`llama3.1`。別モデルを使う場合は
`AnjoOllamaExecutor(model_name="...")`を変更する。

**OpenAI API版**:
`src/openai_agent_loop.py`は`OpenAIAnjoExecutor`クラスのみを提供するテンプレートで、
単体の実行用`__main__`は無い。呼び出し側で以下のように使う。
```python
from src.openai_agent_loop import OpenAIAnjoExecutor

agent = OpenAIAnjoExecutor(workspace_root="jail_workspace", api_key="sk-...")
agent.run_task("タスクの指示内容")
```
`openai`パッケージは`run_task()`実行時に初めてimportされるため、未インストールでも
本ファイルをimportするだけなら例外は発生しない。

## 🌀 メタトロンの統括（完全自動化防衛ループ、`revelations/`へレポート出力）
ラジエル(偵察)→サマエル(ローカルOllamaによる攻撃コード生成)→天使(Blue Team、
Gabriel静的解析+Sandalphon動的隔離検証)→ガブリエル(Markdownレポート生成)の
一連を1サイクルとして自動実行する。実行には**Ollama**(デフォルトモデル`llama3.1`)
と**Dockerデーモン**の両方が必要(Sandalphon層が実行前にコンテナ内で動的検証するため)。

```
python src/metatron_orchestrator.py
```
実行結果は`revelations/gabriel_revelation_<サイクルID>.md`に記録される。デフォルトは
1サイクルのみ。複数サイクル回す場合はコード側で
`MetatronOrchestrator().execute_holy_war(cycles=N)`を呼ぶ。

## 🔑 証明書（ataraxia_certificate.json）の再発行
[2026-10改訂] 以前は`provisioning_agent.py`実行後に`ataraxia_certificate.json`と
`maquina_gatekeeper.py`の両方を即座にコミットする運用だったが、これは提案者が
自分自身を無条件に承認済みにできてしまう自己署名の構造的欠陥だったため、
Armageddon・Zadkielと同じ「提案キューイング＋人間承認」パターンに改めた
（詳細はGRIMOIRE.md §O参照）。

ローカルマシンでのみ実行すること（ハードウェア指紋がマシン固有のため）。
```
python adapters/provisioning_agent.py
```
これにより`sefer/provisioning_pending.json`に提案がキューイングされる。
`maquina_gatekeeper.py`・`ataraxia_certificate.json`はまだ変更されない。

### 承認待ち提案の確認・昇格
```
python tools/promote_provisioning_seal.py --list
python tools/promote_provisioning_seal.py --approve "<client_id>"
python tools/promote_provisioning_seal.py --reject  "<client_id>"
```
`--approve`実行後、更新された`ataraxia_certificate.json`と`maquina_gatekeeper.py`
（公開鍵が反映される）の両方をコミットすること。

## 📦 経典（公開配布物）のビルドと検査
pip配布用の`sefer`単体パッケージ（経典）を実際にビルドし、ライセンス証明書機構
（ゲートキーパー）やTartarus（闘技場）が一切混入していないことを検査する。
公開配布（PyPI等へのアップロード）の前に必ず実行すること。
```
python tools/build_public_scripture.py
```
✅ 検査合格と表示された場合のみ、`dist/sefer-*.tar.gz` を公開配布してよい。

## 🚑 緊急プロトコル（自己免疫疾患の治療）
メタトロンの過学習により `open` などのシステム基盤が禁止され、テストが動かなくなった場合に、
ルール帳を初期のクリーンな状態に強制リセットする。

PowerShell:
```
Set-Content -Path "sefer/raziel_ledger.json" -Value '{"banned_events": ["os.system", "subprocess.Popen", "os.remove", "os.rmdir", "os.rename", "socket.connect", "urllib.Request"]}' -Encoding UTF8
```

bash:
```
cat > sefer/raziel_ledger.json << 'EOF'
{"banned_events": ["os.system", "subprocess.Popen", "os.remove", "os.rmdir", "os.rename", "socket.connect", "urllib.Request"]}
EOF
```
