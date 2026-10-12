"""
tests/test_secure_oracle_feed_quota_persistence.py
======================================================
src/secure_oracle_feed.py の EconomicDefenseLimiter の回帰テスト。
GRIMOIRE.md §AQ 参照。

背景: 旧実装は「1日あたりのAPIリクエスト上限(max_daily_requests)」を
名乗っていたが、カウントをインスタンスのメモリ上の変数としてのみ保持
しており、スクリプトを再実行するたびに0から再始動していた。つまり
実際には「1プロセス実行あたりの上限」でしかなく、繰り返し実行すれば
何度でも上限を回避できた。

本テストは、(1) 同一日内であればプロセス(インスタンス)をまたいでも
カウントが引き継がれ、上限で確実に遮断されること、(2) 日付が変われば
カウントがリセットされ、新しい日の上限まで再び許可されること、の2点を
固定する。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def limiter_env(tmp_path, monkeypatch):
    # google.generativeai / ollama / aegis_system 等のimportに失敗しても
    # EconomicDefenseLimiter自体はこれらに依存しないため、モジュール全体の
    # importではなく、クラス定義だけを切り出して読み込む。
    import importlib
    import types

    # secure_oracle_feed.py はモジュールレベルで google.generativeai・ollama・
    # aegis_system・angelic_evolution をimportしており、このテスト環境には
    # 存在しない可能性がある。それらをスタブ化してから本体をimportする。
    stub_names = ["ollama", "google", "google.generativeai", "aegis_system", "angelic_evolution"]
    saved = {}
    for name in stub_names:
        saved[name] = sys.modules.get(name)
        sys.modules[name] = types.ModuleType(name)
    sys.modules["aegis_system"].AegisSystem = type("AegisSystem", (), {"__init__": lambda self: None})
    sys.modules["angelic_evolution"].EvolvingAngel = type("EvolvingAngel", (), {"__init__": lambda self: None})

    try:
        if "secure_oracle_feed" in sys.modules:
            mod = importlib.reload(sys.modules["secure_oracle_feed"])
        else:
            import secure_oracle_feed as mod
    finally:
        for name in stub_names:
            if saved[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved[name]

    state_path = tmp_path / "oracle_feed_quota.json"
    monkeypatch.setattr(mod.EconomicDefenseLimiter, "STATE_PATH", state_path)
    return mod


def test_quota_persists_across_new_instances_within_same_day(limiter_env, monkeypatch):
    """[脆弱性修正の核心] 同一日内であれば、新しいインスタンス(プロセス再起動を
    模擬)を作っても、以前のインスタンスが消費した回数が引き継がれ、
    上限に達したら確実に遮断されること。"""
    import time as _time_mod
    monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
    mod = limiter_env

    limiter1 = mod.EconomicDefenseLimiter(max_daily_requests=3, cooldown_seconds=0)
    limiter1.wait_and_check()
    limiter1.wait_and_check()

    # プロセス再起動を模擬: 新しいインスタンス(current_requestsは無い=永続化された状態のみを見る)
    limiter2 = mod.EconomicDefenseLimiter(max_daily_requests=3, cooldown_seconds=0)
    limiter2.wait_and_check()  # これで本日3回目(上限)

    with pytest.raises(SystemExit, match="日次APIリクエスト上限"):
        limiter2.wait_and_check()  # 4回目は遮断される


def test_quota_resets_on_a_new_day(limiter_env, monkeypatch):
    """[回帰防止] 日付が変わればカウントがリセットされ、新しい日の上限まで
    再び許可されること。"""
    import json

    import time as _time_mod
    monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
    mod = limiter_env

    # 前日分の「上限到達済み」状態を直接書き込む
    mod.EconomicDefenseLimiter.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(mod.EconomicDefenseLimiter.STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"date": "2000-01-01", "count": 999}, f)

    limiter = mod.EconomicDefenseLimiter(max_daily_requests=3, cooldown_seconds=0)
    # 前日の999回は無関係であり、今日はまだ0回目として許可されること
    limiter.wait_and_check()
    limiter.wait_and_check()
    limiter.wait_and_check()
    with pytest.raises(SystemExit):
        limiter.wait_and_check()


def test_state_file_records_today_utc_date_and_count(limiter_env, monkeypatch):
    """[回帰防止] 永続化されたJSONの内容そのもの(日付キー・カウント)を固定する。"""
    import datetime
    import json

    import time as _time_mod
    monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
    mod = limiter_env

    limiter = mod.EconomicDefenseLimiter(max_daily_requests=5, cooldown_seconds=0)
    limiter.wait_and_check()

    with open(mod.EconomicDefenseLimiter.STATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["date"] == datetime.datetime.utcnow().strftime("%Y-%m-%d")
    assert data["count"] == 1
