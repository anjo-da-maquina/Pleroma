# 履歴書・経歴書用 実績サマリー文

貼り付け用。文字数制限に応じて短縮版・長版を使い分けてください。

---

## 日本語版

### 短縮版(3〜4行)

生成AIが書くコード・AIエージェントが運用するシステムの品質保証に個人的な危機意識を持ち、QAエンジニアの視点から赤チーム/青チーム方式の個人プロジェクト「Pleroma」を継続運用。AIエージェントに自身のコードを攻撃・検証させ、発見した脆弱性81件を実機で検証の上修正し、約50件の継続的回帰テスト(CI)として定着させた。

### 長版(5〜6行、面接ネタとして)

QAエンジニアとして、生成AIの普及に伴う「AIが作る成果物の品質を誰が継続的に保証するのか」という課題に個人的な危機意識を持ち、オープンソースの個人プロジェクト「Pleroma」を立ち上げ継続運用中。AIエージェント自身に赤チーム(攻撃)・青チーム(防御検証)の反復を行わせ、発見した脆弱性(§A〜§CC、計81件)を都度実機のCI環境で検証・修正し、再発防止のための回帰テスト(約50件の常設監査スクリプト)として恒久化。すべての修正は`git stash`による自己レッドチーム(修正前への一時復元→検知失敗の確認→復元→検知成功の確認)を経て初めて完了とする運用ルールを自ら敷き、「対策したつもり」を機械的に排除する検証プロセスを実践している。

---

## English version

### Short (3–4 lines)

Personally concerned, as a QA engineer, with who verifies the quality of what generative AI produces, I run an ongoing open-source project ("Pleroma") where AI agents attack and verify their own code in a repeated red-team/blue-team cycle. 81 logged vulnerabilities have been found, verified on live infrastructure, fixed, and locked in as ~50 standing CI regression checks.

### Long (5–6 lines, for interviews)

As a QA engineer, I became personally concerned with a specific question raised by the rise of generative AI: who actually verifies, on an ongoing basis, the quality of what AI writes and runs? I started and continue to run "Pleroma," an open-source personal project where AI agents attack their own code in a repeated red-team/blue-team cycle, and every real finding (81 logged entries, §A through §CC) is verified on live CI infrastructure before being fixed, then locked in as one of roughly 50 standing automated regression checks. I enforce a self-imposed rule that no fix counts as done until it passes a self-red-team pass — reverting the fix with `git stash`, confirming the check correctly fails, then restoring it and confirming it passes — a mechanical way of eliminating "I think I fixed it" from the process.
