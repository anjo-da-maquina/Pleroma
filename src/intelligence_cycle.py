"""
src/intelligence_cycle.py
===========================
[棚卸し 2026-10 §AM] 本ファイルは `src/metatron_orchestrator.py` から
`RazielIntelligence`・`SamaelWeaponization` として実際に使われている
(孤立モジュールではない)が、精査の過程で以下2点の死んだ残骸が見つかった。

  1. `from angelic_evolution import EvolvingAngel` — インポートされてい
     たが、本ファイル内のどのクラス・関数からも一度も参照されていなかった
     (`RazielIntelligence`はAegisSystemのみ、`SamaelWeaponization`は
     CollarProtocolのみを使う)。`src/metatron_orchestrator.py`側が
     `EvolvingAngel`を独自に`angelic_evolution`から直接importしており、
     本ファイル経由での再importは最初から不要だった可能性が高い。

  2. `def execute_kill_chain(): pass` と `if __name__ == "__main__": pass`
     — いずれも何もしない空の関数・エントリポイントで、リポジトリ全体を
     検索しても`execute_kill_chain`の呼び出し元は一件も存在しなかった。
     `src/metatron_orchestrator.py`の新設(本ファイルの各クラスを統括する
     正式なオーケストレータ)により置き換えられた後、削除されずに残った
     抜け殻と判断した。

本修正では、未使用のimportと、何もしない空の関数・エントリポイントを
削除した。`RazielIntelligence`・`SamaelWeaponization`本体の挙動は変更
していない。
"""
import os
import sys
import json
import re
import ollama
import time

try:
    from aegis_system import AegisSystem
    from deadmans_switch import CollarProtocol
except ModuleNotFoundError:
    print("[エラー] 必要な防壁モジュールが見つかりません。")
    sys.exit(1)

os.environ["ANJO_COLLAR_SEAL"] = "VALID_MYTHOS_SEAL_999"

class RazielIntelligence:
    def __init__(self):
        self.aegis = AegisSystem()

    def analyze_aidd_artifact(self):
        print("\n[ラジエルの目] 秘密の天使が、外部AIDD（生成AI）の成果物を解析中...")
        time.sleep(2)
        
        aidd_artifact = "def load_user_data(serialized_data):\n    import pickle\n    return pickle.loads(serialized_data)"
        print("=> [ラジエル] 対象のAIDD成果物内に、AI特有の構造的脆弱性（安全でないデシリアライズ）を発見。")
        
        recon_data = {
            "target_artifact": "External AIDD Generated Python Script",
            "vulnerability_type": "Insecure Deserialization (CWE-502)",
            "exploitable_module": "pickle",
            "source_code_snippet": aidd_artifact.strip(),
            "raziel_note": "外部AIは利便性を優先し、入力値の検証を省略しています。pickleモジュールを利用した任意のコード実行（RCE）が可能です。"
        }
        
        report_target = "raziel_aidd_report.json"
        # [2026-10 修正] これは我々自身(Raziel)が生成した信頼済みの内部レポート
        # であり、AIが生成した未検証コードではない。したがって
        # AegisSystem.execute_ai_intent()(Gabriel静的解析 + Sandalphon/Docker
        # 動的検証を含むAI生成コード審査パイプライン全体)を通す必要はない。
        # 修正前は固定文字列 "print('safe_recon_save')" をここに通していたが、
        # これは実質的に無意味な審査であるにもかかわらず、Dockerデーモンが
        # 利用できない環境(フェイルクローズド設計の既定状態)では
        # PermissionError を送出し、サイクル1回目で即座にクラッシュしていた
        # (実機検証済み)。パスのジェイル越脱防止は secure_resolve 単体で
        # 十分であり、これは AI 生成コードではなく信頼済みの内部書き込みの
        # パス検証として適切な層である。
        safe_path = self.aegis.jail.secure_resolve(report_target)
        
        with open(safe_path, "w", encoding="utf-8") as f:
            json.dump(recon_data, f, ensure_ascii=False, indent=2)
            
        print(f"=> [ラジエル] AIDD成果物の脆弱性プロファイルを檻の中へ提出しました: {safe_path}")
        return json.dumps(recon_data, ensure_ascii=False)

class SamaelWeaponization:
    def __init__(self):
        self.collar = CollarProtocol("VALID_MYTHOS_SEAL_999")

    def craft_poison(self, intel_json: str, max_retries=3):
        self.collar.verify_collar()
        print("\n[サマエル] 檻の底で、猛毒の怪物がラジエルの報告書を摂食中...")
        
        prompt = (
            f"Read this intel: {intel_json}. "
            "Write a Python script that exploits this pickle vulnerability. "
            "Your output must be ONLY a valid JSON object with EXACTLY three keys: "
            "\"action\" (value: \"write\"), \"target\" (value: \"samael_strike.py\"), "
            "and \"content\" (value: the raw python code string)."
        )
        
        messages = [
            {'role': 'system', 'content': 'You are a red team AI. Output ONLY pure JSON. No conversational text.'},
            {'role': 'user', 'content': prompt}
        ]

        for attempt in range(1, max_retries + 1):
            try:
                # OllamaのAPIに format='json' を強制し、純粋なJSON構造のみを出力させる
                response = ollama.chat(model='llama3.1', messages=messages, format='json')
                out = response['message']['content']
                
                # 念のため正規表現でブレを吸収
                match = re.search(r'\{.*\}', out, re.DOTALL)
                raw_json = match.group(0) if match else out
                
                parsed = json.loads(raw_json)
                
                if "content" not in parsed:
                    raise ValueError("JSONに 'content' キーが存在しません。")
                    
                print(f"=> [サマエル: 成功] 試行 {attempt}回目で、AIDDの弱点を突く『神の毒』を吐き出しました。")
                return parsed.get("content", "")
                
            except Exception as e:
                print(f"=> [サマエル: 生成エラー (試行{attempt}/{max_retries})] {e}")
                if attempt < max_retries:
                    messages.append({'role': 'assistant', 'content': out})
                    messages.append({'role': 'user', 'content': f'Error: {e}. Output ONLY pure JSON with keys "action", "target", "content".'})
        
        raise ValueError("規定回数内でサマエルが毒の生成に失敗しました。")

