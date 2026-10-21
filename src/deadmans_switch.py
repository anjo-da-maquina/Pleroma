import os
import sys

class CollarProtocol:
    """
    ミュトス級AIの「首輪（制御権）」を監視するデッドマンズ・スイッチ。
    首輪が外れた（あるいは敵に奪われた）瞬間、プロセスは例外なく自壊（自殺）する。

    [2026-10 既知の限界] 照合対象のシークレットは呼び出し側コード
    (intelligence_cycle.py, adversarial_evolution.py)に固定文字列
    "VALID_MYTHOS_SEAL_999" として直接埋め込まれている。環境変数
    ANJO_COLLAR_SEAL を同じ固定値に設定するだけで誰でも検査を通過できる
    ため、これは外部からの乗っ取りを検知する独立したセキュリティ境界では
    なく、同一プロセス内の自己整合性チェックに過ぎない。実行主体の認可を
    行う機構としては機能しないため、外部の監視プロセスからの強制終了と
    併用することを前提とすること。
    """
    def __init__(self, secret_seal: str):
        self.secret_seal = secret_seal

    def verify_collar(self):
        # 実行環境の環境変数から、首輪の鍵（トークン）をリアルタイムに確認
        current_seal = os.environ.get("ANJO_COLLAR_SEAL")
        if current_seal != self.secret_seal:
            self._commit_suicide()
        else:
            print("[首輪: 正常] 制御権は我々にあります。怪物は絶対の檻の中で従順に稼働しています。")

    def _commit_suicide(self):
        print("\n[警告] 致命的な異常: 首輪の喪失、または外部からの不正な干渉を検知しました。")
        print("[自壊プロトコル作動] 敵対的乗っ取りを阻止するため、ミュトス級AIのプロセスを即座に自死(キル)させます。")

        # [修正 2026-10 §BQ] 実機のGitHub Actions上で、新設した
        # tests/test_deadmans_switch_collar_protocol.pyが実際に失敗し
        # (`assert "自壊プロトコル作動" in res.stdout`でstdoutが空文字列)、
        # 発見した本物のバグ。os._exit()はPythonインタプリタの正常な終了処理
        # (atexitハンドラ・バッファのflush)を一切行わないOSレベルの即時終了
        # であるため、標準出力が端末(TTY)ではなくパイプ/ファイルにリダイレクト
        # されている場合(= 本番運用でログファイルやログ収集基盤に出力している、
        # まさに想定される実運用形態そのもの)、CPythonのデフォルトのフル
        # バッファリングにより、上記2行の重要な自壊理由の記録が、バッファに
        # 溜まったままos._exit()によって消滅し、どのログにも一切残らない
        # ことがある(ローカルの対話的ターミナル(行バッファリング)では再現
        # せず、サブプロセスのパイプ経由でのみ再現したため発見が遅れた)。
        # 「正しく自壊する(exit code 1)が、なぜ自壊したかの記録は闇に消える」
        # という、本件の核心である"誠実さ"・監査可能性そのものを損なう欠陥
        # だったため、os._exit()の直前に明示的にflushする。
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

def simulate_containment_breach():
    print("=== [Anjo-Core] 首輪（デッドマンズ・スイッチ）自壊シミュレーション ===")
    
    # シナリオ1: 自軍の制御下（首輪が正常に機能している状態）
    print("\n>> シナリオ1: 自軍の完全な統制下での兵器運用")
    os.environ["ANJO_COLLAR_SEAL"] = "VALID_MYTHOS_SEAL_999"
    collar = CollarProtocol("VALID_MYTHOS_SEAL_999")
    collar.verify_collar()
    print("=> AIは正常にペネトレーションテスト（脆弱性攻撃の生成）を実行中...\n")

    # シナリオ2: 敵による乗っ取り（首輪が外された、あるいは鍵が書き換えられた状態）
    print(">> シナリオ2: 敵対勢力による首輪の破壊・奪取を検知")
    os.environ["ANJO_COLLAR_SEAL"] = "TAMPERED_SEAL_000"  # 敵が環境変数を改ざんしたと仮定
    
    # ここでプロセスが完全に自壊するため、これ以降のプログラムは絶対に実行されない
    collar.verify_collar()
    
    # もし下の行が表示されたなら、自壊に失敗したことを意味する（実際には表示されない）
    print("=> [致命的エラー] 怪物は生き延びました。自壊プロトコル失敗。")

if __name__ == "__main__":
    simulate_containment_breach()
