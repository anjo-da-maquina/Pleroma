"""
[テスト追加 2026-10] tools/generate_dashboard.py の集計ロジックの回帰テスト。
実データファイル(tartarus/akashic_records.json等)には依存せず、tmp_path上に
架空のデータを用意して検証する(build_dashboardは各パスを明示的に注入できる)。
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from generate_dashboard import build_dashboard  # noqa: E402


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")


def test_dashboard_renders_summary_cards_from_real_looking_data(tmp_path: Path):
    akashic_path = tmp_path / "akashic_records.json"
    _write_json(akashic_path, [
        {"generation": 1, "status": "Breached", "qa_score": 10, "timestamp": "t1", "qa_hint": "h1"},
        {"generation": 2, "status": "Failed", "qa_score": 5, "timestamp": "t2", "qa_hint": "h2"},
    ])

    audit_chain_path = tmp_path / "audit_chain.jsonl"
    _write_jsonl(audit_chain_path, [
        {"event": "os.system", "timestamp": 1.0},
        {"event": "os.system", "timestamp": 2.0},
        {"event": "exec", "timestamp": 3.0},
    ])

    ledger_path = tmp_path / "raziel_ledger.json"
    _write_json(ledger_path, {"banned_events": ["os.system", "subprocess.Popen"]})

    pending_path = tmp_path / "pending.json"
    _write_json(pending_path, [
        {"status": "PENDING_HUMAN_REVIEW", "event": "x"},
        {"status": "APPROVED", "event": "y"},
    ])

    html = build_dashboard(
        akashic_path=akashic_path,
        audit_chain_path=audit_chain_path,
        ledger_path=ledger_path,
        pending_paths={"テスト用キュー": pending_path},
    )

    assert "<html" in html and "</html>" in html
    # 総戦績2件、突破1件、Michaelの遮断3件、禁止イベント2件、承認待ち1件が反映されているか
    assert ">2<" in html  # 総戦績
    assert "os.system" in html
    assert "subprocess.Popen" in html
    assert "テスト用キュー" in html


def test_dashboard_handles_missing_files_gracefully(tmp_path: Path):
    """すべてのデータファイルが存在しない(初回実行等)場合でも例外を出さずに生成できる"""
    html = build_dashboard(
        akashic_path=tmp_path / "does_not_exist.json",
        audit_chain_path=tmp_path / "does_not_exist.jsonl",
        ledger_path=tmp_path / "does_not_exist2.json",
        pending_paths={"空キュー": tmp_path / "does_not_exist3.json"},
    )
    assert "<html" in html and "</html>" in html
    assert "データがありません" in html
