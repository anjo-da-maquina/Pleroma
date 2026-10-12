"""
[脆弱性修正 2026-10 §AX] tools/auto_red_team.py の回帰テスト。

このツールは「難読化した攻撃ペイロードが、ガブリエル(静的解析)・
ミカエル(動的フック)の二重防壁を本当に突破できないか」を自動生成・実行
して検証する、歴史の長いレッドチーム用スクリプトである。しかし精査の結果、
以下2つの独立したバグにより、実際には防壁を一度も試していないまま
「全攻撃が防壁を突破した(Successful Bypasses: 48)」という、完全に偽の
致命的敗北を報告していたことが判明した:

  1. `inquisition(payload)` の戻り値(Findingのリスト)を一度も確認せず、
     ただ呼ぶだけで次に進んでいた。`inquisition()`は違反を検知しても
     例外を送出しない純粋関数であるため、直後の`except PermissionError:`
     は一度も発火し得ない死んだコードだった。
  2. `exec(payload, {})` が `with Sanctum(...):` の外で直接呼ばれており、
     冒頭の`awaken()`だけでは監査フックが実質的に無効(§AU/armageddon.py
     と同種の欠陥)だった。さらに、Sanctumが実際に遮断する際の例外は
     `sefer.LossOfAtaraxia`(`BaseException`直接継承)だが、旧コードは
     `except RuntimeError as e: if "Michael's Sword" in str(e):`という、
     型も文言も一致しない死んだ捕捉を書いていた。

本テストは、修正後に実際に`python tools/auto_red_team.py`をサブプロセスで
実行し、(1) Successful Bypassesが0件であること(=本物のGabriel/Sanctumが
正しく機能していること)、(2) Blocked by Gabrielが実際に48件(全件)である
こと(=戻り値が本当に確認されていること)を実機で固定する。
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_auto_red_team():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "auto_red_team.py")],
        cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=60,
    )


def test_auto_red_team_reports_zero_bypasses_against_real_defenses():
    """[脆弱性の核心] 本物のGabriel静的解析とSanctum動的フックに対して
    実行すると、難読化ペイロードは1件も実行まで到達しない(0 bypasses)
    こと。修正前はここが常に48(全件)になっていた。"""
    result = _run_auto_red_team()
    assert "Successful Bypasses     : 0" in result.stdout, (
        f"防壁を本当に試さずに偽の突破を報告している可能性がある:\n{result.stdout}"
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_auto_red_team_actually_invokes_gabriel_check_on_every_payload():
    """[回帰防止] `inquisition()`の戻り値が実際に確認されていること
    (=死んだ`except PermissionError:`に戻っていないこと)の確認。
    全48件の攻撃ペイロードは、いずれもリテラルな`getattr`/`__import__`/
    `exec`識別子を含むため、Gabrielの裸名チェックで全件検知されるはずで
    あり、Blocked by Gabrielは48になるはずである。"""
    result = _run_auto_red_team()
    assert "Blocked by Gabriel      : 48" in result.stdout, (
        f"Gabrielの検知結果が実際には確認されていない可能性がある:\n{result.stdout}"
    )
