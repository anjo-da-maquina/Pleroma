# スコープ外改名 提案書(未実行・提案のみ)

**作成日**: 2026-11-04
**ステータス**: 提案のみ。本ドキュメントに記載された改名は **一切実行していない**。
`git mv`・文字列置換・コミットは行わず、調査結果と提案を記すのみ。

**対象外とした理由**: `angels/` 配下55スクリプトの改名(ブランチ
`rename/angels-plain-english-names`、`main`へマージ済み・CI確認済み)の依頼時点で、
以下5項目は明示的にスコープ外・提案のみとされていたため。

---

## 1. `sefer/` パッケージ

### 現状
- `pyproject.toml` で `name = "sefer"` として **PyPI配布物そのものの名前**になっている
  (`sefer.egg-info/` も存在、`description = "Zero-Trust OS Fortress for Local AI Agents"`)。
- 実体は3つの役割を持つ:
  1. `sefer/__init__.py` の `Sanctum` クラス — `allowed_dirs`/`allowed_hosts`/`restrict_reads`を
     指定してネスト可能な「許可範囲」を宣言するコンテキストマネージャ。
  2. 同ファイルの `_michael_absolute_defense`(`sys.addaudithook`に登録される監査フック本体)
     — ファイル書き込み・ソケット通信・mmap・fd経由書き込み等、約10種の脱獄経路を実機検証の上で遮断する。
  3. 同ファイルの `inquisition()`(AST静的解析による危険コード検出、`Finding`データクラスを返す)。
  4. `sefer/audit_chain.py` の `SignedAuditChain`(HMAC-SHA256鍵付きハッシュ連鎖の監査ログ)。
- コード内コメントでは「Michael」という天使名で各防御ロジックを指している箇所が複数残っている
  (`sefer/__init__.py`内の`_michael_absolute_defense`という関数名自体が天使名)。

### 提案名
`runtime_guard`(パッケージ名・PyPI配布名として)

理由: 実行時(`sys.addaudithook`)に常駐して脱獄経路を遮断する防御基盤という実際の役割をそのまま表す。
`Sanctum`→`ScopedPolicy`、`inquisition()`→`scan_source()`、`_michael_absolute_defense`→
`_runtime_audit_hook` のような内部名の追随改名も合わせて検討可能(ただし関数名改名は別途影響調査が必要)。

### 影響範囲(高リスク)
- `.py`ファイル中の `sefer` 参照: **113ファイル**。
- **PyPI配布名の変更を含む**ため、既存ユーザーが `pip install sefer` で導入している場合、
  パッケージ名変更は破壊的変更(breaking change)になる。`pyproject.toml`の`name`変更は
  実質的にメジャーバージョンアップ相当の判断が必要。
- `tartarus/armageddon_core.py` が `from sefer import ALWAYS_PASSTHROUGH_AUDIT_EVENTS` のように
  パッケージ名をハードコードでimportしている(ドリフト防止のための単一の正、§BJのコメント参照)。
- `.gitignore`/`.dockerignore` 中の `sefer/.audit_signing_key` 等、ファイルパスとしての参照も多数。

---

## 2. `tartarus/` ディレクトリ

### 現状
- `tartarus/armageddon.py` — 起動直後に `_verify_creators_air()`(創造主のMACアドレスのハッシュ照合)を行い、
  不一致なら即座に終了する。**創造主のローカルPC以外では絶対に起動しない設計**のゲート。
- `tartarus/armageddon_core.py` — MACアドレスチェックに依存しない「純粋ロジック」部分を分離したもの。
  Red Team(Lucifer)側がBlue Team(Sefer)側の防御を突破しようと試行し続ける自己対戦エンジンで、
  新たな禁止イベント案を`akashic_records.json`に記録し、人間が承認すれば`sefer/raziel_ledger.json`
  (Razielの台帳)に反映される仕組み。
- `tartarus/akashic_records.json` — 自己対戦の世代ごとの試行記録(ペイロード・成否・スコア等)。

### 提案名
`adversarial_training/`(ディレクトリ名)、内部ファイルは
`armageddon.py`→`local_only_selfplay_gate.py`、
`armageddon_core.py`→`selfplay_engine_core.py`、
`akashic_records.json`→`selfplay_history.json`

理由: 「創造主のローカル環境限定で動く、攻撃側・防御側の自己対戦による新しい脆弱性発見エンジン」
という実際の役割をそのまま表す。

### 影響範囲
- `.py`ファイル中の `tartarus` 参照: **27ファイル**。
- `sefer/__init__.py`側のコメント(§BJ)が`tartarus/armageddon_core.py`を名指しで参照しているため、
  2のパッケージ名改名(1.)と同時に行う場合は相互参照の更新順序に注意が必要。
- ローカル限定ゲートという設計意図上、CI上では実行されない(MACアドレス不一致で即終了)ため、
  CI側への影響は小さいと推測されるが、実機(創造主のPC)での動作確認が改名後に必須。

---

## 3. `sandalphon_jail`(`src/sandalphon_jail.py`)

### 現状
- Docker + seccompプロファイルによる**OSレベルの強制サンドボックス実行**を提供する。
  `run_in_sandalphon(code, timeout)` が実体。
- 2026-10の修正で、それまで「CLIから手動で呼ぶだけの独立ツールで、AI実行経路からは一度も
  呼ばれていなかった(=Docker隔離は任意のおまけ)」という設計上の欠陥を修正し、
  `aegis_system.py` から**強制的(mandatory)な動的検証**として呼ばれるようになった。
- **重要**: 既にリネーム済みの `angels/guard_seccomp_syscall.py`・`angels/guard_container_capabilities.py`・
  `angels/guard_docker_sandbox_enforcement_decay.py` は、この `sandalphon_jail` の**実行結果を検査する**
  側(監査役)であり、`sandalphon_jail`自体(実行主体)とは明確に別物。改名時にこの非対称性
  (「監査対象のjail実行器」 vs 「それを監査する3本のguard」)を混同しないこと。

### 提案名
`src/docker_sandbox_executor.py`

理由: 「Dockerコンテナ内でコードをseccompプロファイル付きで実行する」という実際の機能そのもの。

### 影響範囲
以下15ファイルで `sandalphon_jail` という識別子が参照されている(grep確認済み):
- `src/sandalphon_jail.py` (本体)
- `src/metatron_orchestrator.py`
- `src/aegis_system.py`
- `src/cassiels_veil.py`
- `.github/workflows/anjo_da_maquina_protocol.yml`
- `GRIMOIRE.md`
- `tests/test_sandalphon_jail_mount_permissions.py`
- `tests/test_guard_seccomp_syscall.py`
- `tests/test_guard_docker_sandbox_enforcement_decay.py`
- `tests/test_aegis_sandalphon_mandatory.py`
- `tests/test_guard_container_capabilities.py`
- `tests/test_sandalphon_seccomp_profile.py`
- `angels/guard_seccomp_syscall.py`
- `angels/guard_container_capabilities.py`
- `angels/guard_docker_sandbox_enforcement_decay.py`

テストファイル名 `test_sandalphon_jail_mount_permissions.py`・`test_sandalphon_seccomp_profile.py`も
改名対象になる(今回の`angels/`改名で使った`git mv`手順がそのまま適用可能)。

---

## 4. `maquina_gatekeeper.py`

### 現状
- トップレベル単一ファイルで、以下を含む:
  - `LossOfAtaraxia` 例外クラス
  - `ZKAuditTrail`(HMAC-SHA256鍵付きハッシュ連鎖で署名する監査証跡クラス、`sefer/audit_chain.py`の
    `SignedAuditChain`とは別実装で、2つが「同種のログを別々に実装している」ことがGRIMOIRE.md §AHで
    言及されている)
  - `_GLOBAL_SANCTUARY_LOCK`/`is_sanctuary_sealed()`/`set_sanctuary_sealed()` —
    プロセス全体で共有する「封鎖(seal)」状態。これが破られるとAI実行を完全停止する最終防衛線。
  - `get_machine_id()` とRSA公開鍵 — おそらく創造主のマシン認証に関連(関数名から推測、
    今回は内部ロジックの全文は未読のため確定的な説明ではない)。

### 提案名
`runtime_audit_gatekeeper.py`

理由: 「ランタイムの監査証跡("ZKAuditTrail")+プロセス全体の最終封鎖スイッチ」を一つのファイルに
まとめた、実行時監査と緊急停止のゲートキーパーという役割をそのまま表す。

### 影響範囲(最大リスク)
- `.py`ファイル中の `maquina_gatekeeper` 参照: **42ファイル**(今回提案対象中最多)。
- `_GLOBAL_SANCTUARY_LOCK`/`is_sanctuary_sealed`等はプロセス全体の状態を扱う既存の脆弱性修正
  (2026-10のスレッドローカル化バグ)の対象そのものであり、改名作業中に誤ってこの排他制御ロジックに
  触れると、`angels/`リネームで確立した「ロジック自体には絶対に手を入れず、識別子の置換のみ行う」
  という安全な手順の遵守が特に重要になる。
- ファイル名自体に「maquina(機械)」という作者名由来の語を含み、リポジトリ名`anjo-da-maquina`
  (創造主のGitHubアカウント名)とも関連するため、**5のPleroma改名と合わせて検討すると
  整合性が取りやすい**(逆に、片方だけ改名すると用語の一貫性が崩れる可能性がある)。

---

## 5. "Pleroma" 自体(プロジェクト名)

### 現状
- リポジトリ名・`GRIMOIRE.md`のタイトル・CI通知文言等で `Pleroma`(グノーシス主義の用語、
  「充溢」「万物の総体」を意味する)が使われている。
- `.py`/`.md`/`.yml`中の参照: **17件**。

### 提案名
(複数案。最終判断はプロジェクト運営者=創造主の判断を優先すべき事項のため、ここでは選択肢の提示のみ)
- `AIDD-Sentinel` — AI駆動開発(AIDD)の見張り番、という役割直結の名前。
- `ZeroTrust-AIDD` — 本プロジェクトの核心コンセプト(ゼロトラスト)を直接含む名前。

### 影響範囲(実行しない場合でも記録しておくべき注意点)
- **リポジトリ名そのものの変更**は、GitHubリダイレクト設定・PyPI配布物名(1.と連動する場合)・
  既存のGitHub Actionsワークフロー内のバッジURL・READMEやドキュメント内の絶対URLリンクなど、
  リポジトリ外部から見える識別子すべてに波及する、今回の提案5件中で最も影響範囲が広く、
  最も「後戻りしにくい」変更になる。
- 実際に `anjo-da-maquina/Pleroma.git` → `anjo-da-maquina/pleroma.git`(小文字化)への移行は
  既に発生済み(リモートがリダイレクト通知を出している)ことから、「表記揺れ」自体への感度は
  既に一定ある状態と見られるが、プロジェクト名の全面改名は別次元の判断であり、
  今回のangels改名のような機械的な`git mv`では完結しない(README・ドキュメント・外部リンク・
  CIバッジ・コミット履行履歴上の過去コミットメッセージ中の言及など、コード上の識別子置換の
  範囲を超える)。

---

## まとめ(優先順位の目安・あくまで提案)

| 対象 | 参照ファイル数 | 破壊的変更の有無 | リスク |
|---|---|---|---|
| `sandalphon_jail` | 15 | なし(内部識別子のみ) | 低〜中 |
| `tartarus/` | 27 | なし(ローカル限定・CI非実行) | 低〜中 |
| `sefer/` | 113 | **あり**(PyPI配布名) | 高 |
| `maquina_gatekeeper.py` | 42 | なし(内部識別子のみ、ただし最終防衛線ロジックに近接) | 中〜高 |
| Pleroma(プロジェクト名) | 17 | **あり**(リポジトリ外部識別子全般) | 最高 |

`sandalphon_jail`・`tartarus/`は`angels/`改名と同じ手順(`git mv`+識別子置換+テスト前後比較)が
そのまま適用できる低リスク候補。`sefer/`と`Pleroma`自体は外部に公開された名前の変更を伴うため、
実行判断には別途、創造主自身による「破壊的変更を受け入れるか」の意思決定が必要。

本書に記載した内容は一切実行していない。改名を進める場合は、`angels/`改名で確立した
「draft-first承認(提案→承認→ブランチ実行→検証→merge→実機CI確認)」の手順を個別に適用することを推奨する。
