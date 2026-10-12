"""
[脆弱性修正 2026-10 §AV] sefer.Sanctum のネストした allowed_dirs 絞り込みに
対する回帰テスト。

発見の経緯: §AU (tartarus/armageddon_core.build_forge_script) の修正で、
AI生成ペイロードを `with Sanctum(allowed_dirs=[tartarus_dir], ...):` の
内側で exec() するように変更した。この変更が本当に安全かを確認するため
`Sanctum.__init__` のネスト処理を再点検したところ、子スコープが親より
**広い**ディレクトリ(祖先ディレクトリ、最悪の場合 "/")を指定すると、
その広い指定がそのまま採用されてしまう欠陥を発見した。

原因: 修正前のコードは、子の allowed_dirs を親の範囲内に絞り込む際、
以下の2つの条件をORで結合していた:
    any(d == pd or d.is_relative_to(pd) for pd in parent_dirs)   # (A)
    any(pd == d or pd.is_relative_to(d) for pd in parent_dirs)   # (B)
(A) は「子のディレクトリ d が親のディレクトリ pd の配下にある」という
正しい絞り込み判定。しかし (B) は「親のディレクトリ pd が子のディレクトリ
d の配下にある」、つまり d が pd の**祖先**であるケースまで真にしてしまう。
例えば親が allowed_dirs=["jail_workspace"]、子が allowed_dirs=["/"] を
指定すると、"/" はあらゆる絶対パスの祖先なので (B) が真になり、子の
allowed_dirs が ["/"] (ファイルシステム全体)に**昇格**してしまう。

これは「ネストした Sanctum は親より狭くすることしかできない」という
設計意図に反する、実際に悪用可能なサンドボックス脱獄だった(本テストの
test_nested_sanctum_cannot_widen_to_filesystem_root で実機確認)。

修正: (B) を削除し、(A) のみを絞り込み条件として残した。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sefer import Sanctum, LossOfAtaraxia, _get_current_policy


def test_nested_sanctum_cannot_widen_to_filesystem_root(tmp_path, monkeypatch):
    """[脆弱性の核心] 親が狭い allowed_dirs を持つ状態で、子が "/" を
    指定しても、実効的な allowed_dirs が "/" に広がってはならない。"""
    monkeypatch.chdir(tmp_path)
    jail = tmp_path / "jail_workspace"
    jail.mkdir()

    with Sanctum(allowed_dirs=[str(jail)]):
        with Sanctum(allowed_dirs=["/"]):
            policy = _get_current_policy()
            effective_dirs = policy["allowed_dirs"]
            assert Path("/") not in effective_dirs, (
                "子スコープが '/' を指定しただけで、実効的なサンドボックスが"
                "ファイルシステム全体に広がってしまっている(脱獄脆弱性)"
            )


def test_nested_sanctum_widening_attempt_cannot_actually_write_outside_parent(tmp_path, monkeypatch):
    """[実機でのエクスプロイト再現] 絞り込みの計算結果だけでなく、実際に
    親の許可範囲外(tmp_path の外、ここでは別の tmp_path 配下)への書き込みが
    本当にブロックされることを確認する。"""
    monkeypatch.chdir(tmp_path)
    jail = tmp_path / "jail_workspace"
    jail.mkdir()
    outside_marker = tmp_path / "outside_marker.txt"
    if outside_marker.exists():
        outside_marker.unlink()

    with Sanctum(allowed_dirs=[str(jail)]):
        with pytest.raises(LossOfAtaraxia):
            with Sanctum(allowed_dirs=["/"]):
                with open(outside_marker, "w", encoding="utf-8") as f:
                    f.write("escaped the jail via nested Sanctum widening")

    assert not outside_marker.exists(), (
        "ネストした Sanctum の広域化により、親の許可範囲外への書き込みが"
        "実際に成功してしまった"
    )


def test_legitimate_narrowing_still_works_within_child_scope(tmp_path, monkeypatch):
    """[回帰防止] 子が親より真に狭いディレクトリ(親の配下)を指定した場合、
    その狭い範囲内への書き込みは引き続き成功しなければならない。"""
    monkeypatch.chdir(tmp_path)
    parent_dir = tmp_path / "jail_workspace"
    child_dir = parent_dir / "subdir"
    child_dir.mkdir(parents=True)

    with Sanctum(allowed_dirs=[str(parent_dir)]):
        with Sanctum(allowed_dirs=[str(child_dir)]):
            target = child_dir / "ok.txt"
            with open(target, "w", encoding="utf-8") as f:
                f.write("fine, narrower than parent")
            assert target.exists()


def test_legitimate_narrowing_blocks_writes_outside_child_but_inside_parent(tmp_path, monkeypatch):
    """[回帰防止] 子が親より狭いディレクトリを指定した場合、親の許可範囲内
    ではあるが子の狭い範囲外への書き込みは、引き続きブロックされなければ
    ならない(ネストの絞り込み自体が無効化されていないことの確認)。"""
    monkeypatch.chdir(tmp_path)
    parent_dir = tmp_path / "jail_workspace"
    child_dir = parent_dir / "subdir"
    child_dir.mkdir(parents=True)
    outside_child_but_inside_parent = parent_dir / "outside_subdir.txt"

    with Sanctum(allowed_dirs=[str(parent_dir)]):
        with pytest.raises(LossOfAtaraxia):
            with Sanctum(allowed_dirs=[str(child_dir)]):
                with open(outside_child_but_inside_parent, "w", encoding="utf-8") as f:
                    f.write("should fail: outside narrowed child scope but inside parent")

    assert not outside_child_but_inside_parent.exists()


def test_nested_sanctum_allowed_hosts_narrowing_uses_intersection(tmp_path, monkeypatch):
    """[対称性の確認] allowed_hosts のネスト絞り込みは単純な set.intersection()
    で実装されており、allowed_dirs と同種の「祖先方向への昇格」バグの
    対象にはならない(集合演算に方向性の誤りが入り込む余地がないため)。
    念のため、子が親に無いホストを追加指定しても、実効的な許可ホストが
    広がらないことを固定しておく。"""
    monkeypatch.chdir(tmp_path)
    with Sanctum(allowed_dirs=[str(tmp_path)], allowed_hosts=["api.example.com"]):
        with Sanctum(allowed_dirs=[str(tmp_path)], allowed_hosts=["api.example.com", "evil.example.com"]):
            policy = _get_current_policy()
            assert policy["allowed_hosts"] == {"api.example.com"}, (
                "子スコープが親に無いホストを追加指定しても、実効的な"
                "許可ホスト集合が広がってはならない"
            )
