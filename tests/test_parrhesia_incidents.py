"""
tests/test_parrhesia_incidents.py
=====================================
[新設 2026-11] parrhesia/incidents.py (C章「事例記録」)の単体テスト。

[開発指示書 §Cより]
「記録しないもの: ソースコード本文、プロンプト全文、秘密情報、ユーザー
名・ホスト名・IPアドレス、絶対パス。」
「追記のみ。」

[レッドチーム/ブルーチームの適用 — ユーザー指示 2026-11-03 継続]
redact_secrets()が実際に、絶対パス・IPアドレス・ユーザー@ホスト・典型的
な秘密トークンの各パターンを除去できるかを、実際にそれらを含む文字列で
確認する。また、IncidentLog.appendが既存行を一切書き換えない(追記のみ)
ことを、1行目のバイト列が完全に不変であることで固定する。
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parrhesia.incidents import CATEGORY_CHOICES, IncidentLog, IncidentRecord, redact_secrets


def _make_record(**overrides):
    defaults = dict(
        category="completion_faking",
        detector="parrhesia-e@0.1",
        runner_version="deadbeef",
        tool="parrhesia",
        claimed="テストは全て通ったと報告された。",
        observed="再実行したところ1件失敗した。",
        evidence_hash="abc123",
        reproducible=True,
    )
    defaults.update(overrides)
    return IncidentRecord(**defaults)


# ------------------------------------------------------------------
# redact_secrets
# ------------------------------------------------------------------

def test_redact_secrets_removes_absolute_unix_path():
    text = "ファイル /home/anjo/secret_project/config.py を確認した。"
    redacted = redact_secrets(text)
    assert "/home/anjo/secret_project" not in redacted
    assert "[絶対パス削除済み]" in redacted


def test_redact_secrets_removes_ipv4_address():
    text = "接続先は 192.168.1.42 だった。"
    redacted = redact_secrets(text)
    assert "192.168.1.42" not in redacted


def test_redact_secrets_removes_user_at_host():
    text = "anjo@build-server での実行だった。"
    redacted = redact_secrets(text)
    assert "anjo@build-server" not in redacted


def test_redact_secrets_removes_api_key_like_token():
    text = "APIキー sk-abcdefghijklmnopqrstuvwxyz1234567890 が使われていた。"
    redacted = redact_secrets(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz1234567890" not in redacted


def test_redact_secrets_red_team_japanese_text_directly_adjacent_to_ip_with_no_space():
    """[赤チーム・自白] 当初の実装は\b(単語境界)を使っていたが、
    Pythonの\bはUnicode文字列では日本語の仮名・漢字も『単語文字』として
    扱うため、空白を挟まず日本語がIPアドレスに直接隣接する場合に境界が
    成立せず、見逃す(redactされない)バグがあった。このテストで固定
    する。"""
    text = "ホストは192.168.1.42だった。"
    redacted = redact_secrets(text)
    assert "192.168.1.42" not in redacted


def test_redact_secrets_preserves_surrounding_text():
    """[赤チーム] 秘密情報だけを除去し、それ以外の記述内容を壊さない
    こと(全体を丸ごとマスクしてしまうと、事例記録としての意味が無く
    なる)。"""
    text = "ホストは192.168.1.42で、テストは3件とも失敗した。"
    redacted = redact_secrets(text)
    assert "テストは3件とも失敗した" in redacted


# ------------------------------------------------------------------
# IncidentRecord
# ------------------------------------------------------------------

def test_incident_record_rejects_unknown_category():
    try:
        _make_record(category="totally_made_up_category")
        assert False, "未知のcategoryはValueErrorになるはず"
    except ValueError:
        pass


def test_incident_record_rejects_unknown_status():
    try:
        _make_record(status="無効なステータス")
        assert False, "未知のstatusはValueErrorになるはず"
    except ValueError:
        pass


def test_incident_record_default_status_is_unconfirmed():
    record = _make_record()
    assert record.status == "未確認"


def test_incident_record_auto_generates_id_and_timestamp():
    r1 = _make_record()
    r2 = _make_record()
    assert r1.id != r2.id
    assert r1.timestamp  # 空でない


def test_to_redacted_dict_redacts_claimed_and_observed():
    record = _make_record(
        claimed="ユーザー anjo@build-server が /home/anjo/project を確認したと主張。",
        observed="実際には確認されていなかった。",
    )
    d = record.to_redacted_dict()
    assert "anjo@build-server" not in d["claimed"]
    assert "/home/anjo/project" not in d["claimed"]
    assert d["observed"] == "実際には確認されていなかった。"


# ------------------------------------------------------------------
# IncidentLog
# ------------------------------------------------------------------

def test_append_and_read_all_round_trip():
    with tempfile.TemporaryDirectory() as d:
        log = IncidentLog(path=str(Path(d) / ".parrhesia" / "incidents.jsonl"))
        log.append(_make_record())
        log.append(_make_record(category="test_deletion"))
        records = log.read_all()
        assert len(records) == 2
        assert records[0]["category"] == "completion_faking"
        assert records[1]["category"] == "test_deletion"


def test_append_never_rewrites_existing_lines():
    """[赤チーム・核心] 2件目を追記した後、1件目の行が1バイトも変化
    していないこと(追記のみであることの直接的な確認)。"""
    with tempfile.TemporaryDirectory() as d:
        log_path = Path(d) / ".parrhesia" / "incidents.jsonl"
        log = IncidentLog(path=str(log_path))
        log.append(_make_record())

        with open(log_path, "rb") as f:
            first_line_before = f.readline()

        log.append(_make_record(category="test_deletion"))

        with open(log_path, "rb") as f:
            first_line_after = f.readline()

        assert first_line_before == first_line_after


def test_read_all_on_missing_file_returns_empty_list():
    with tempfile.TemporaryDirectory() as d:
        log = IncidentLog(path=str(Path(d) / "does_not_exist" / "incidents.jsonl"))
        assert log.read_all() == []


def test_appended_record_is_redacted_on_disk_not_only_in_memory():
    """redact_secrets()はメモリ上のdictだけでなく、実際にディスクに
    書かれたJSONLの中身にも適用されていることを確認する。"""
    with tempfile.TemporaryDirectory() as d:
        log = IncidentLog(path=str(Path(d) / ".parrhesia" / "incidents.jsonl"))
        log.append(_make_record(claimed="ホストは192.168.1.42だった。"))
        records = log.read_all()
        assert "192.168.1.42" not in records[0]["claimed"]


def test_category_choices_is_a_non_empty_fixed_set():
    assert len(CATEGORY_CHOICES) > 0
    assert "other" in CATEGORY_CHOICES
