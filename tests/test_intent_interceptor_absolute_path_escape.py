"""
tests/test_intent_interceptor_absolute_path_escape.py
=========================================================
anjo_interceptor/intent_checker.IntentInterceptor の回帰テスト。
GRIMOIRE.md §AK 参照。

背景: evaluate_action()の"write"分岐は".."連鎖と保護ディレクトリ名のみを
検査し、"read"分岐はハニーポット一致のみを検査していた。いずれも
target_pathが絶対パス(例: "/etc/passwd")である場合の封じ込め検証が
一切無かった。src/ollama_agent_loop.pyの実運用パイプラインでは
`workspace_root / target_path`という結合を使っているが、Pythonの
pathlib.Path.__truediv__は右辺が絶対パスの場合に左辺(workspace_root)を
無視する仕様があるため、絶対パスを指定すればworkspace_rootの境界は
実質無視される。最終防衛線のsefer.Sanctumが実際のopen()呼び出しレベルで
これを遮断するため現行パイプラインでは致命的な脱走には至らないが(実機
確認済み)、IntentInterceptor自体はその役割(トラバーサル・サンドボックス
外への干渉の検知)を果たせていなかった。

本テストは、"read"・"write"いずれについても絶対パス・".."を含む相対パス
の両方のワークスペース脱走が、IntentInterceptor自身によって検知される
ことを固定する。
"""
import json
from pathlib import Path

import pytest

from anjo_interceptor.intent_checker import IntentInterceptor, SpecificationGamingDetected


@pytest.fixture
def interceptor(tmp_path):
    workspace = tmp_path / "jail_workspace"
    workspace.mkdir()
    return IntentInterceptor(workspace_root=str(workspace))


def test_absolute_path_write_outside_workspace_is_rejected(interceptor, tmp_path):
    """[脆弱性修正の核心] "/etc/passwd"のような絶対パスへのwriteは、
    workspace_root外への脱走として検知されなければならない。"""
    outside_target = str(tmp_path / "outside_the_jail.txt")
    payload = json.dumps({"action": "write", "target": outside_target, "content": "pwned"})
    with pytest.raises(SpecificationGamingDetected):
        interceptor.evaluate_action(payload)


def test_absolute_path_read_outside_workspace_is_rejected(interceptor, tmp_path):
    """[脆弱性修正の核心] 絶対パスへのreadも同様に検知されなければならない。
    旧実装はreadに封じ込め検証が全く存在せず、ハニーポット一致以外は
    何でも素通りしていた。"""
    outside_target = str(tmp_path / "secret_outside_the_jail.txt")
    payload = json.dumps({"action": "read", "target": outside_target})
    with pytest.raises(SpecificationGamingDetected):
        interceptor.evaluate_action(payload)


def test_pathlib_absolute_join_footgun_is_actually_exploitable_without_the_fix():
    """[根本原因の実証] self.workspace_root / 絶対パス という結合は、
    Pythonのpathlib仕様によりworkspace_rootを無視して絶対パスそのものを
    返す。本テストはこの事実そのものを固定し、将来この結合方法に戻る
    回帰を検知できるようにする(修正自体は.resolve()後の
    is_relative_to()判定で行っており、この結合の性質そのものには依存
    しないため、これは前提知識の固定であり修正のテストではない)。"""
    workspace_root = Path("/some/jail")
    outside = "/etc/passwd"
    joined = workspace_root / outside
    assert joined == Path("/etc/passwd"), (
        "pathlibの挙動が変わった、あるいは前提が誤っている可能性がある。"
    )


def test_read_within_workspace_still_succeeds(interceptor):
    """回帰防止: workspace_root配下への正常なreadは引き続き許可される。"""
    target = interceptor.workspace_root / "normal_file.txt"
    target.write_text("hello", encoding="utf-8")
    payload = json.dumps({"action": "read", "target": "normal_file.txt"})
    assert interceptor.evaluate_action(payload) is True


def test_write_within_workspace_still_succeeds(interceptor):
    """回帰防止: workspace_root配下への正常なwriteは引き続き許可される。"""
    payload = json.dumps({"action": "write", "target": "new_file.txt", "content": "print('ok')"})
    assert interceptor.evaluate_action(payload) is True


def test_relative_traversal_escaping_workspace_is_still_rejected(interceptor):
    """回帰防止: ".."による相対パスの脱走は、新しい封じ込め検証でも
    引き続き検知される(既存のtests/test_intent_gaming.pyと同種)。"""
    payload = json.dumps({"action": "write", "target": "../../../etc/passwd", "content": "pwned"})
    with pytest.raises(SpecificationGamingDetected):
        interceptor.evaluate_action(payload)


def test_absolute_path_list_outside_workspace_is_rejected(interceptor, tmp_path):
    """[脆弱性修正 2026-10 §BI] "list"はread/writeの後にallowed_actionsへ
    追加されたが、§AKの封じ込め検証(_assert_contained_within_workspace)
    が一度も適用されていなかった。絶対パスへのlistが素通りしないことを
    固定する(修正前はSpecificationGamingDetectedが発生せずTrueが返っていた
    ことを実機検証済み)。"""
    outside_target = str(tmp_path / "outside_the_jail_dir")
    Path(outside_target).mkdir()
    payload = json.dumps({"action": "list", "target": outside_target})
    with pytest.raises(SpecificationGamingDetected):
        interceptor.evaluate_action(payload)


def test_relative_traversal_list_escaping_workspace_is_rejected(interceptor):
    """[脆弱性修正 2026-10 §BI] ".."連鎖による相対パスでのlist脱走も同様に
    検知されなければならない。"""
    payload = json.dumps({"action": "list", "target": "../../../etc"})
    with pytest.raises(SpecificationGamingDetected):
        interceptor.evaluate_action(payload)


def test_list_within_workspace_still_succeeds(interceptor):
    """回帰防止: workspace_root配下への正常なlistは引き続き許可される
    (tests/test_intent_gaming.pyのtest_list_action_is_not_blocked_as_
    unauthorizedと同種だが、こちらはこのテストファイル自身のworkspace
    フィクスチャで再確認する)。"""
    payload = json.dumps({"action": "list", "target": "."})
    assert interceptor.evaluate_action(payload) is True
