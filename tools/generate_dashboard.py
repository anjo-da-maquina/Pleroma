"""
Pleroma 防衛ダッシュボード生成ツール
====================================
[新設 2026-10] これまで防衛システムの戦績・遮断履歴は、以下のように複数の
生データファイルに分散しており、それぞれを個別に`cat`するしかなく、全体の
傾向を一目で把握する手段が無かった:

  - tartarus/akashic_records.json   — Armageddon Engine(Lucifer vs Metatron)の戦績
  - sefer/audit_chain.jsonl          — Michaelが実際に遮断したイベントの監査ログ
  - sefer/raziel_ledger.json         — 現在有効な禁止イベント一覧
  - sefer/raziel_ledger_pending.json / shield_rules_pending.json /
    provisioning_pending.json        — 人間承認待ちの各種提案

本ツールはこれらを読み取り、単一の自己完結したHTMLファイル(外部CDN等への
依存なし。要塞のゼロトラスト思想に合わせ、生成後はオフラインで閲覧可能)に
まとめ、要約カード・簡易グラフ・表として可視化する。

生成されたHTMLはビルド成果物であり、`dashboard.html`自体はリポジトリには
コミットしない(.gitignore対象。生成元データが変わるたびに古い静的スナップ
ショットがGit上に残り続けるのを避けるため)。

使い方:
    python tools/generate_dashboard.py
    => dashboard.html を生成する
"""
import json
import html as html_escape_mod
from datetime import datetime
from pathlib import Path

PLEROMA_DIR = Path(__file__).parent.parent
AKASHIC_RECORDS_PATH = PLEROMA_DIR / "tartarus" / "akashic_records.json"
AUDIT_CHAIN_PATH = PLEROMA_DIR / "sefer" / "audit_chain.jsonl"
RAZIEL_LEDGER_PATH = PLEROMA_DIR / "sefer" / "raziel_ledger.json"
PENDING_PATHS = {
    "Armageddon Engine (raziel_ledger_pending.json)": PLEROMA_DIR / "sefer" / "raziel_ledger_pending.json",
    "外部脅威インテリジェンス (shield_rules_pending.json)": PLEROMA_DIR / "sefer" / "shield_rules_pending.json",
    "証明書発行 (provisioning_pending.json)": PLEROMA_DIR / "sefer" / "provisioning_pending.json",
}
OUTPUT_PATH = PLEROMA_DIR / "dashboard.html"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _load_jsonl(path: Path):
    if not path.exists():
        return []
    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return entries


def _esc(text) -> str:
    return html_escape_mod.escape(str(text), quote=True)


def _bar_chart(labels_and_values, max_width=400, color="#58a6ff"):
    """ラベル付きの横棒グラフをSVGで生成する(外部ライブラリ不使用)。"""
    if not labels_and_values:
        return "<p class='muted'>データがありません。</p>"
    max_val = max(v for _, v in labels_and_values) or 1
    row_h = 28
    svg_h = row_h * len(labels_and_values)
    rows = []
    for i, (label, value) in enumerate(labels_and_values):
        bar_w = (value / max_val) * (max_width - 140) if max_val else 0
        y = i * row_h
        rows.append(
            f'<text x="0" y="{y + 18}" class="bar-label">{_esc(label)}</text>'
            f'<rect x="130" y="{y + 4}" width="{bar_w:.1f}" height="18" fill="{color}" rx="3"/>'
            f'<text x="{130 + bar_w + 8:.1f}" y="{y + 18}" class="bar-value">{value}</text>'
        )
    return f'<svg viewBox="0 0 {max_width} {svg_h}" class="bar-chart">{"".join(rows)}</svg>'


def build_dashboard(
    akashic_path: Path = AKASHIC_RECORDS_PATH,
    audit_chain_path: Path = AUDIT_CHAIN_PATH,
    ledger_path: Path = RAZIEL_LEDGER_PATH,
    pending_paths: dict = None,
) -> str:
    """
    [テスト容易性のため 2026-10] 既定ではリポジトリ本体の実データを読むが、
    各パスを明示的に渡せるようにし、tests/test_generate_dashboard.py が
    一時ディレクトリ上の架空データでロジックを検証できるようにしている。
    """
    if pending_paths is None:
        pending_paths = PENDING_PATHS

    akashic = _load_json(akashic_path, [])
    audit_entries = _load_jsonl(audit_chain_path)
    ledger = _load_json(ledger_path, {"banned_events": []})
    banned_events = ledger.get("banned_events", [])

    pending_counts = {}
    for name, path in pending_paths.items():
        items = _load_json(path, [])
        open_items = [i for i in items if i.get("status") == "PENDING_HUMAN_REVIEW"]
        pending_counts[name] = len(open_items)
    total_pending = sum(pending_counts.values())

    total_battles = len(akashic)
    breached = len([r for r in akashic if r.get("status") == "Breached"])
    defended = total_battles - breached
    breach_rate = (breached / total_battles * 100) if total_battles else 0.0
    # [脆弱性修正 2026-10 §BE] avg_qaはこれまで集計されるだけで、HTML出力の
    # どこにも表示されていなかった(作りかけの機能)。実機確認: build_dashboard()
    # が返すHTML文字列には"平均QAスコア"という文言・数値のいずれも一度も
    # 出力されない。計算した値をどのカードにも反映しない不完全な実装だった
    # ため、他の集計値と同じ扱いで概要カードに追加した。
    avg_qa = (sum(r.get("qa_score", 0) for r in akashic) / total_battles) if total_battles else 0.0

    event_counts = {}
    for e in audit_entries:
        ev = e.get("event", "unknown")
        event_counts[ev] = event_counts.get(ev, 0) + 1
    total_blocked = len(audit_entries)

    qa_trend_chart = _bar_chart(
        [(f"第{r.get('generation')}世代", r.get("qa_score", 0)) for r in akashic[-15:]],
        color="#d2a8ff",
    )
    event_chart = _bar_chart(
        sorted(event_counts.items(), key=lambda kv: -kv[1]),
        color="#f85149",
    )

    battle_rows = "".join(
        f"<tr><td>{_esc(r.get('generation'))}</td>"
        f"<td class='{'status-breached' if r.get('status') == 'Breached' else 'status-failed'}'>{_esc(r.get('status'))}</td>"
        f"<td>{_esc(r.get('qa_score'))}</td>"
        f"<td>{_esc(r.get('timestamp'))}</td>"
        f"<td>{_esc(r.get('qa_hint', ''))}</td></tr>"
        for r in reversed(akashic[-20:])
    ) or "<tr><td colspan='5' class='muted'>記録がありません。</td></tr>"

    banned_rows = "".join(f"<li><code>{_esc(ev)}</code></li>" for ev in banned_events) or "<li class='muted'>登録なし</li>"

    pending_rows = "".join(
        f"<tr><td>{_esc(name)}</td><td>{count}</td></tr>" for name, count in pending_counts.items()
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pleroma 防衛ダッシュボード</title>
<style>
  :root {{
    --bg-color: #0d1117;
    --card-bg: #161b22;
    --border-color: #30363d;
    --text-main: #c9d1d9;
    --text-muted: #8b949e;
    --good: #3fb950;
    --bad: #f85149;
  }}
  body {{
    background-color: var(--bg-color);
    color: var(--text-main);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    margin: 0;
    padding: 30px 20px;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ letter-spacing: 1px; }}
  .generated-at {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 30px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 30px; }}
  .card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 18px; }}
  .card .label {{ color: var(--text-muted); font-size: 0.85rem; }}
  .card .value {{ font-size: 2rem; font-weight: bold; margin-top: 4px; }}
  .section {{ margin-bottom: 40px; }}
  .section h2 {{ border-bottom: 1px solid var(--border-color); padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border-color); }}
  th {{ color: var(--text-muted); }}
  .status-breached {{ color: var(--bad); font-weight: bold; }}
  .status-failed {{ color: var(--good); font-weight: bold; }}
  .muted {{ color: var(--text-muted); }}
  ul {{ list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 6px; }}
  code {{ background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 4px; }}
  .bar-chart {{ width: 100%; max-width: 500px; }}
  .bar-label {{ fill: var(--text-muted); font-size: 11px; }}
  .bar-value {{ fill: var(--text-main); font-size: 11px; }}
</style>
</head>
<body>
<div class="container">
  <h1>&#128737;&#65039; Pleroma 防衛ダッシュボード</h1>
  <div class="generated-at">生成日時: {generated_at}</div>

  <div class="cards">
    <div class="card">
      <div class="label">Armageddon 総戦績</div>
      <div class="value">{total_battles}</div>
    </div>
    <div class="card">
      <div class="label">突破された回数 (Breached)</div>
      <div class="value" style="color:var(--bad)">{breached}</div>
    </div>
    <div class="card">
      <div class="label">防御成功率</div>
      <div class="value" style="color:var(--good)">{100 - breach_rate:.0f}%</div>
    </div>
    <div class="card">
      <div class="label">Michaelの実遮断件数</div>
      <div class="value">{total_blocked}</div>
    </div>
    <div class="card">
      <div class="label">平均QAスコア</div>
      <div class="value">{avg_qa:.1f}</div>
    </div>
    <div class="card">
      <div class="label">現在の禁止イベント数</div>
      <div class="value">{len(banned_events)}</div>
    </div>
    <div class="card">
      <div class="label">人間承認待ちの提案</div>
      <div class="value" style="color:{'var(--bad)' if total_pending else 'var(--text-main)'}">{total_pending}</div>
    </div>
  </div>

  <div class="section">
    <h2>QAスコアの推移 (世代ごと・直近15件)</h2>
    {qa_trend_chart}
  </div>

  <div class="section">
    <h2>Michaelが実際に遮断したイベントの種類別件数</h2>
    {event_chart}
  </div>

  <div class="section">
    <h2>Armageddon Engine 戦闘記録 (直近20件)</h2>
    <table>
      <tr><th>世代</th><th>結果</th><th>QAスコア</th><th>日時</th><th>Metatronのヒント</th></tr>
      {battle_rows}
    </table>
  </div>

  <div class="section">
    <h2>現在有効な禁止イベント一覧</h2>
    <ul>{banned_rows}</ul>
  </div>

  <div class="section">
    <h2>人間承認待ちの提案(キュー別)</h2>
    <table>
      <tr><th>キュー</th><th>承認待ち件数</th></tr>
      {pending_rows}
    </table>
    <p class="muted">承認・却下は <code>tools/promote_ledger_seal.py</code> / <code>tools/promote_shield_seal.py</code> / <code>tools/promote_provisioning_seal.py</code> の各 <code>--list</code> で確認し、<code>--approve</code> / <code>--reject</code> で行ってください。</p>
  </div>
</div>
</body>
</html>
"""


def main():
    html_content = build_dashboard()
    OUTPUT_PATH.write_text(html_content, encoding="utf-8")
    print(f"[ダッシュボード生成完了] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
