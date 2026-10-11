"""
src/uriel_phoenix.py
=====================
[2026-10 実運用統合] 以前は `jail_workspace` / `anjo-da-maquina` という
固定パスのみを対象とする `__main__` 専用のデモスクリプトだった。

「致命的な侵入が確定した後の焦土作戦」という設計意図上、通常タスク完了ごと
に自動実行するのは不適切(AIの正常な作業成果まで毎回消去してしまう)。
これは `tools/promote_ledger_seal.py` / `tools/promote_shield_seal.py` と
同じ「人間が状況を確認した上で明示的に起動する」運用ツールに位置づける。
実際の起動は `tools/incident_reset.py`(新規)から行う。

本修正で以下を一般化した:
  - `core_dir` / `talisman` を引数で指定可能にし、実際の運用対象である
    `WorkspaceJail.base_dir`(既定 "jail_workspace")を直接渡せるようにした。
  - `talisman` は任意(None可)。元のデモは `samaels_curse.py` の護符マーカー
    ファイル慣習に合わせていたが、実運用上は隔離領域のリセットのみで十分な
    ケースが多いため、指定しない場合はスキップする。
  - `announce` 引数で、運用ツールから静かに呼び出す場合の演出出力を抑制できる。

[脆弱性修正 2026-10] `core_dir`/`talisman`を一般化して任意のパスを
指定可能にした際、`shutil.rmtree()`/`Path.unlink()`に対する経路の安全性
検証を一切追加していなかった。本クラスは`tools/incident_reset.py`という、
人間がインシデント対応中に手で呼び出す運用ツールの中核であり、たとえば
インシデント対応で動揺した操作者が`--core-dir /`や`--core-dir ~`、あるいは
単純な誤入力(空文字列・"."等)を指定してしまった場合、確認プロンプトを
一度通過しさえすれば、ファイルシステムのルートやホームディレクトリ、
あるいは`/etc`のような極めて浅い(=被害範囲が破滅的に広い)ディレクトリを
丸ごと`rmtree()`してしまう構造的な欠陥があった。これは「致命的な侵入後の
焦土作戦」という強力な破壊的操作である以上、操作者の単純な入力ミスに対する
最低限の安全装置(フールプルーフ)を備えるべきである。

解決した脆弱性クラス自体を列挙する:
  1. 解決後のパスがファイルシステムのルート(Windowsのドライブルート含む)
     そのものである。
  2. 解決後のパスがホームディレクトリそのものである。
  3. 解決後のパスの深さ(ルートからの階層数)が極端に浅い(既定: 2階層未満。
     例: "/etc", "/home", "/var" 等のシステム標準ディレクトリを誤って
     対象にしてしまうことを防ぐ)。
テスト用の一時ディレクトリ(pytestの`tmp_path`等)は十分な深さを持つため、
本チェックの影響を受けない。意図的に浅いパスを対象にする必要がある場合は
`allow_shallow_path=True`を明示的に渡すこと(既定はFalse=安全側)。
"""
import shutil
import time
from pathlib import Path


class UrielPhoenixUnsafeTargetError(Exception):
    """rmtree()/unlink()の対象パスが危険すぎる(ルート・ホーム・極端に浅い)場合に送出する。"""
    pass


_MIN_SAFE_PATH_DEPTH = 2


def _ensure_safe_destructive_target(path: Path, kind: str, allow_shallow_path: bool) -> Path:
    resolved = path.resolve()

    if str(resolved) == resolved.anchor:
        raise UrielPhoenixUnsafeTargetError(
            f"[安全装置作動] {kind}の対象がファイルシステムのルート({resolved})です。実行を拒否します。"
        )

    try:
        home = Path.home().resolve()
    except Exception:
        home = None
    if home is not None and resolved == home:
        raise UrielPhoenixUnsafeTargetError(
            f"[安全装置作動] {kind}の対象がホームディレクトリ({resolved})そのものです。実行を拒否します。"
        )

    if not allow_shallow_path:
        depth = len(resolved.relative_to(resolved.anchor).parts)
        if depth < _MIN_SAFE_PATH_DEPTH:
            raise UrielPhoenixUnsafeTargetError(
                f"[安全装置作動] {kind}の対象({resolved})はルートから{depth}階層しかなく、"
                "システム標準ディレクトリの誤指定の疑いがあります。本当に意図したものであれば"
                "allow_shallow_path=True(CLIでは--allow-shallow-path)を明示してください。"
            )

    return resolved


class UrielPhoenix:
    def __init__(self, core_dir="jail_workspace", talisman=None, allow_shallow_path: bool = False):
        self.core_dir = Path(core_dir)
        self.talisman = Path(talisman) if talisman else None
        self.allow_shallow_path = allow_shallow_path

    def scorched_earth_and_rebirth(self, announce: bool = True):
        if announce:
            print("=== [Anjo-Core] ウリエルの炎（破壊と再生の焦土作戦） ===\n")
            print("[警告] 致命的な侵入を検知。要塞 Anjo-Core の完全掌握が確認されました。")
            print("=> [ウリエル降臨] 穢れた要塞を浄化するため、神の炎が解き放たれます...\n")

        # 【安全装置】実際に破壊する前に、対象パスがルート・ホーム・
        # 極端に浅いシステムディレクトリでないことを検証する。
        _ensure_safe_destructive_target(self.core_dir, "隔離領域(core_dir)", self.allow_shallow_path)
        if self.talisman is not None:
            _ensure_safe_destructive_target(self.talisman, "護符(talisman)", self.allow_shallow_path)

        # 【破壊】すべてを焼却し、敵の足場を消滅させる
        if announce:
            print(">> フェーズ1: 破壊（Scorched Earth）")
        if self.core_dir.exists():
            shutil.rmtree(self.core_dir)
            if announce:
                print(f"[-] 隔離領域 '{self.core_dir}' および内部のすべての汚染データを焼却しました。")

        if self.talisman is not None and self.talisman.exists():
            self.talisman.unlink()
            if announce:
                print(f"[-] 穢れた護符 '{self.talisman}' を灰に帰しました。")

        # 【再生】純白の初期状態としてシステムを復活させる
        if announce:
            print("\n>> フェーズ2: 転生（Phoenix Rebirth）")
        self.core_dir.mkdir(parents=True, exist_ok=True)
        if announce:
            print(f"[+] 純白の隔離領域 '{self.core_dir}' を再構築しました。")

        if self.talisman is not None:
            self.talisman.touch()
            if announce:
                print(f"[+] 新たな護符 '{self.talisman.name}' が灰の中から転生しました。")

        if announce:
            print("\n[戦果] 敵は掌握したはずのすべてを失い、我々は無傷の要塞を取り戻しました。")
            print("ウリエルによる浄化と復活が完了しました。")

        return {"core_dir": str(self.core_dir), "talisman": str(self.talisman) if self.talisman else None}


def simulate_breach_demo():
    """元の `__main__` デモと同じ挙動(固定パス・演出あり)を保つための互換関数。"""
    print("=== [Anjo-Core] ウリエルの炎 デモシミュレーション ===\n")
    time.sleep(1)
    UrielPhoenix(core_dir="jail_workspace", talisman="anjo-da-maquina").scorched_earth_and_rebirth()


if __name__ == "__main__":
    simulate_breach_demo()
