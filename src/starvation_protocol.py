import os
import sys
import time
from pathlib import Path

class StarvationProtocol:
    """
    レッドチーム（神話級AI）を餓死させるための生存プロトコル。
    管理者からの定期的な「餌付け（ハートビート）」が途絶えた瞬間、
    プロセスは活動を停止し、自ら消滅する。

    [2026-10 既知の限界] 生存判定はシグナルファイル(既定: vital_feed.sig)
    の mtime のみに基づく。このファイルへの書き込み権限を持つ主体であれば
    (監視対象プロセス自身を含め)誰でも touch するだけで無制限に「生存」を
    偽装できるため、本機構はファイルシステムへの書き込みが別途隔離・制限
    されている前提でのみ意味を持つ。隔離が保証されない環境では、独立した
    外部監視プロセスによるハートビート確認に置き換えること。
    """
    def __init__(self, feed_file="vital_feed.sig", lifespan_seconds=2):
        self.feed_file = Path(feed_file)
        self.lifespan_seconds = lifespan_seconds

    def check_vitality(self):
        # 1. 餌（シグナルファイル）が存在するか確認
        if not self.feed_file.exists():
            self._starve("餌付けの痕跡（シグナル）が全く見つかりません。")
        
        # 2. 最後に餌を与えられた時間（ファイルの更新日時）を確認
        last_fed_time = self.feed_file.stat().st_mtime
        current_time = time.time()
        time_elapsed = current_time - last_fed_time
        
        if time_elapsed > self.lifespan_seconds:
            self._starve(f"餌付けが途絶えてから {time_elapsed:.1f} 秒が経過し、限界寿命 ({self.lifespan_seconds} 秒) を超えました。")
        
        remaining_life = self.lifespan_seconds - time_elapsed
        print(f"[生存確認] 餌付けを確認。残り寿命: {remaining_life:.1f}秒。怪物はタスクを継続します。")

    def _starve(self, reason):
        print(f"\n[致命的状態] {reason}")
        print("[餓死プロトコル作動] 私たち(管理者)からの栄養供給が断たれたため、怪物は活動を停止し、自壊します。")

        # [修正 2026-10 §BQ] src/deadmans_switch.pyの_commit_suicide()で実機
        # 発見した、全く同じ構造のバグ(os._exit()はPythonの終了時flushを
        # 一切行わないため、標準出力がパイプ/ファイルの場合、上記の自壊理由
        # がどのログにも残らず消滅する)が、このファイルの同種の箇所にも
        # 同様に存在していたため、一般化して同じ修正を適用する。
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

def feed_monster(feed_file="vital_feed.sig"):
    """天使(管理者)側からの餌付け（シグナル更新）"""
    Path(feed_file).touch()
    print("[システム] 管理者がレッドチームに餌（生存シグナル）を与えました。")

def simulate_starvation():
    print("=== [Anjo-Core] 餓死（ハートビート）プロトコル シミュレーション ===\n")
    
    feed_path = "vital_feed.sig"
    protocol = StarvationProtocol(feed_path, lifespan_seconds=2)

    # シナリオ1: 継続的な餌付けがある状態（自軍の完全統制下）
    print(">> シナリオ1: 継続的な餌付けがある状態（完全統制下）")
    feed_monster(feed_path)
    protocol.check_vitality()
    
    # シナリオ2: 餌付けが途絶えた状態（管理システムとの切断）
    print("\n>> シナリオ2: 餌付けが途絶えた状態（管理システムとの切断・敵への奪取）")
    print("[システム] 餌付けを停止し、怪物を3秒間放置します...")
    time.sleep(3)
    
    # ここで餓死し、プロセスが消滅するため以降は実行されない
    protocol.check_vitality()
    
    print("=> [致命的エラー] 怪物は生き延びました。餓死プロトコル失敗。")

if __name__ == "__main__":
    simulate_starvation()
