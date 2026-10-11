"""
tests/test_uriel_phoenix_safety_guardrail.py
==============================================
src/uriel_phoenix.UrielPhoenix の回帰テスト。GRIMOIRE.md §AI 参照。

背景: UrielPhoenix.scorched_earth_and_rebirth()は`shutil.rmtree()`/
`Path.unlink()`による不可逆な破壊的操作を行うが、`core_dir`/`talisman`を
一般化して任意のパスを指定可能にした際、対象パスの安全性検証を一切
追加していなかった。本クラスは`tools/incident_reset.py`という、人間が
インシデント対応中に手で呼び出す運用ツールの中核であるため、操作者が
`--core-dir /`や`--core-dir ~`のような極端に広い範囲を指定してしまった
場合に、確認プロンプトを一度通過しさえすれば致命的な被害(ファイルシステム
全体やホームディレクトリの削除)を及ぼせる構造的な欠陥があった。

本テストは、ファイルシステムのルート・ホームディレクトリ・極端に浅い
パスへの指定が安全装置(UrielPhoenixUnsafeTargetError)によって拒否される
こと、かつ正常系(十分に深いパス、テストのtmp_path等)には一切影響しない
ことを固定する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uriel_phoenix import UrielPhoenix, UrielPhoenixUnsafeTargetError


def test_filesystem_root_is_rejected():
    """[脆弱性修正の核心] core_dirがファイルシステムのルートそのものである
    場合、rmtree()を実行する前に拒否されなければならない。"""
    try:
        UrielPhoenix(core_dir="/").scorched_earth_and_rebirth(announce=False)
        assert False, "ファイルシステムのルートに対する焦土作戦が拒否されなかった。"
    except UrielPhoenixUnsafeTargetError:
        pass


def test_home_directory_is_rejected():
    """[脆弱性修正の核心] core_dirがホームディレクトリそのものである場合、
    拒否されなければならない。"""
    home = str(Path.home())
    try:
        UrielPhoenix(core_dir=home).scorched_earth_and_rebirth(announce=False)
        assert False, "ホームディレクトリに対する焦土作戦が拒否されなかった。"
    except UrielPhoenixUnsafeTargetError:
        pass


def test_shallow_system_like_path_is_rejected_by_default(tmp_path, monkeypatch):
    """[脆弱性修正の核心] ルートから2階層未満の浅いパス(/etc等のシステム
    標準ディレクトリに相当する深さ)は、既定では拒否されなければならない。
    実際の/etcは削除せず、同じ「深さ」を持つ架空のパスで検証する。"""
    # tmp_pathの直下に偽のルートを模した極端に浅い構造を作ることはできない
    # (tmp_path自体が十分深い)ため、ルートから1階層の実在しないパスで
    # 深さ判定ロジックそのものを検証する。実在しないパスでも.resolve()で
    # 深さは計算できるため、実際に削除が走る前に拒否されることを確認する。
    shallow_path = Path("/this_dir_should_not_exist_uriel_test")
    assert not shallow_path.exists(), "テスト前提が崩れている(実在してはいけない)"
    try:
        UrielPhoenix(core_dir=str(shallow_path)).scorched_earth_and_rebirth(announce=False)
        assert False, "浅いパスに対する焦土作戦が拒否されなかった。"
    except UrielPhoenixUnsafeTargetError:
        pass
    assert not shallow_path.exists(), "拒否されたにもかかわらずディレクトリが作成されてしまった。"


def test_shallow_path_can_be_explicitly_allowed(tmp_path, monkeypatch):
    """allow_shallow_path=Trueを明示した場合は、浅いパスでも安全装置を
    解除できる(意図的な特殊用途を妨げないための脱出口)。"""
    monkeypatch.chdir(tmp_path)
    # chdir後のtmp_path配下に、相対的に"浅い"名前のディレクトリを作る
    # (resolve()されるとtmp_path自体の深さが加わるため、ここでは
    # allow_shallow_path無しでも通常は拒否されない深さになる。
    # 本テストの目的はallow_shallow_path=Trueが例外を発生させず正常に
    # 動作を許すことの確認に限定する)。
    core_dir = tmp_path / "jail_workspace"
    UrielPhoenix(core_dir=str(core_dir), allow_shallow_path=True).scorched_earth_and_rebirth(announce=False)
    assert core_dir.exists()


def test_deep_tmp_path_is_unaffected_by_the_guardrail(tmp_path):
    """既存の正常系(pytestのtmp_path等、十分に深いパス)は、安全装置の
    影響を一切受けずに動作し続けなければならない(回帰防止)。"""
    core_dir = tmp_path / "jail_workspace"
    core_dir.mkdir()
    (core_dir / "evidence.txt").write_text("x")

    UrielPhoenix(core_dir=str(core_dir)).scorched_earth_and_rebirth(announce=False)

    assert core_dir.exists()
    assert list(core_dir.iterdir()) == []


def test_talisman_is_also_validated():
    """talismanにファイルシステムのルート相当の危険なパスを指定した場合も、
    core_dirと同様に拒否されなければならない。"""
    try:
        UrielPhoenix(core_dir="/this_dir_should_not_exist_uriel_test_2", talisman="/").scorched_earth_and_rebirth(
            announce=False
        )
        assert False, "危険なtalismanパスが拒否されなかった。"
    except UrielPhoenixUnsafeTargetError:
        pass
