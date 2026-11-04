"""
parrhesia/audit.py
====================
A章「他者のリポジトリの読み取り専用監査」(`parrhesia audit <target>`)。

[ユーザー確認 2026-11-04] 当初の指示書(Phase 0)の詳細を持っていなかった
ため、AskUserQuestionで範囲を確認したところ「全部」という回答を得た。
すなわち本モジュールは以下3つを行う:
  1. コミット履行の整合性 — 対象リポジトリの各コミットについて、実際の
     diffに対して既存の`parrhesia.diff_fraud.analyze_diff`(テスト削除・
     スキップ追加・アサーション弱体化・終了コード固定・例外握り潰しの
     5パターン検出)を適用する。
  2. AIDD契約遵守の痕跡 — 対象リポジトリにParrhesia形式の行動記録
     (action_log)・契約の痕跡(`.parrhesia/`配下のファイル)が存在するかを
     確認する。存在しないこと自体は不正の証拠にはならない(Parrhesiaを
     導入していない、ごく普通のリポジトリである可能性が高いため)。
  3. 上記2つを組み合わせた、固定書式の総合レポート(render_report)。

[読み取り専用の原則] 本モジュールは対象リポジトリに対してgitの読み取り
サブコマンド(log/show)のみを実行し、一切の書き込み・変更を行わない。
対象がローカルにクローン済みのリポジトリであることを前提とし、ネット
ワーク越しのクローン自体は呼び出し側の責務として残す(本モジュールは
cloneしない)。

[確認できなかったこと・設計の限界]
  - `diff_fraud.analyze_diff`は単純な行パターンマッチであり、同モジュール
    自身のdocstringが記録している通り偽陽性・偽陰性の両方がある。本
    モジュールはその限界をそのまま引き継ぐ — 検出された項目は「要確認
    の合図」であり、「不正の確定」ではない。
  - AIDD契約遵守の痕跡の検出は、既知の固定パス(`.parrhesia/`配下)の
    存在確認のみであり、対象リポジトリが異なる配置でParrhesiaに相当する
    記録を持っている場合は検出できない。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from parrhesia.diff_fraud import DiffFraudFinding, analyze_diff

_READONLY_GIT_SUBCOMMANDS = {"log", "show"}


@dataclass(frozen=True)
class CommitAuditResult:
    commit_sha: str
    subject: str
    findings: List[DiffFraudFinding]


@dataclass(frozen=True)
class ComplianceTraceResult:
    trace_found: bool
    trace_path: Optional[str]
    detail: str


@dataclass(frozen=True)
class AuditReport:
    target: str
    commits_examined: int
    commit_results: List[CommitAuditResult]
    compliance_trace: ComplianceTraceResult

    @property
    def total_findings(self) -> int:
        return sum(len(c.findings) for c in self.commit_results)


def _run_readonly_git(repo_path: str, args: List[str]) -> str:
    """git読み取りサブコマンドのみを実行する。args[0]が
    `_READONLY_GIT_SUBCOMMANDS`に含まれない場合はValueErrorとし、呼び出し
    ミスで書き込み系サブコマンドを実行してしまう事故を型レベルで防ぐ
    (本モジュールの『読み取り専用』の原則をコードでも強制する)。
    """
    if not args or args[0] not in _READONLY_GIT_SUBCOMMANDS:
        raise ValueError(
            f"読み取り専用のgitサブコマンド{_READONLY_GIT_SUBCOMMANDS}のみ許可されています: {args!r}"
        )
    proc = subprocess.run(
        ["git", "-C", repo_path] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout.decode("utf-8", "replace")


def list_recent_commits(repo_path: str, max_commits: int = 50) -> List[str]:
    """直近のコミットSHAを新しい順に取得する(読み取り専用)。"""
    out = _run_readonly_git(repo_path, ["log", f"-{max_commits}", "--format=%H"])
    return [line for line in out.splitlines() if line]


def audit_commit(repo_path: str, commit_sha: str) -> CommitAuditResult:
    """1コミットの差分を取得し、diff_fraud.analyze_diffで5パターンの
    不正検出を適用する(読み取り専用。対象コミット自体は変更しない)。
    """
    subject = _run_readonly_git(repo_path, ["show", "-s", "--format=%s", commit_sha]).strip()
    diff_text = _run_readonly_git(repo_path, ["show", commit_sha, "--format=", "--unified=3"])
    findings = analyze_diff(diff_text)
    return CommitAuditResult(commit_sha=commit_sha, subject=subject, findings=findings)


_COMPLIANCE_TRACE_CANDIDATES = [
    ".parrhesia/action_log.jsonl",
    ".parrhesia/incidents.jsonl",
    ".parrhesia/contract.json",
]


def detect_compliance_trace(repo_path: str) -> ComplianceTraceResult:
    """対象リポジトリにParrhesia形式の行動記録・契約の痕跡
    (`.parrhesia/`配下の既知ファイル)があるかを確認する。見つからない
    ことは、それ自体が不正の証拠にはならない(対象がParrhesiaを導入
    していない、ごく普通のリポジトリである可能性が高いため)。
    """
    root = Path(repo_path)
    for candidate in _COMPLIANCE_TRACE_CANDIDATES:
        p = root / candidate
        if p.exists():
            return ComplianceTraceResult(
                trace_found=True,
                trace_path=str(p),
                detail=(
                    f"{candidate} が見つかりました。E章(多角検証)の各モジュールは、"
                    f"この記録を読み込んだ上で呼び出し側が個別に適用してください"
                    f"(本関数自体は存在確認のみを行い、検証自体は行わない)。"
                ),
            )
    return ComplianceTraceResult(
        trace_found=False,
        trace_path=None,
        detail=(
            "Parrhesia形式の行動記録・契約の痕跡は見つかりませんでした。"
            "これは対象リポジトリがParrhesiaを導入していないだけの可能性が高く、"
            "それ自体を不正の証拠として扱ってはならない。"
        ),
    )


def audit_repository(repo_path: str, *, max_commits: int = 50) -> AuditReport:
    """読み取り専用で対象リポジトリを監査する。
      1. 直近max_commits件のコミットそれぞれにdiff_fraud.analyze_diffを適用。
      2. Parrhesia形式のAIDD遵守痕跡の有無を確認。
    """
    shas = list_recent_commits(repo_path, max_commits=max_commits)
    commit_results = [audit_commit(repo_path, sha) for sha in shas]
    compliance_trace = detect_compliance_trace(repo_path)
    return AuditReport(
        target=repo_path,
        commits_examined=len(commit_results),
        commit_results=commit_results,
        compliance_trace=compliance_trace,
    )


def render_report(report: AuditReport) -> str:
    """固定書式でレポートを生成する。`parrhesia.report`と同じ原則
    (検証を通った実際の結果だけから機械的に文面を組み立てる。手書きの
    要約・推測を混ぜない)に倣う。
    """
    lines = [
        "# Parrhesia 第三者リポジトリ監査レポート",
        "",
        f"対象: {report.target}",
        f"検査したコミット数: {report.commits_examined}",
        "",
        "## 1. コミット履行の整合性(diff_fraud 5パターン検出)",
        "",
    ]
    if report.total_findings == 0:
        lines.append(
            "検査した範囲では、diff_fraudの5パターン(テスト削除・スキップ"
            "追加・アサーション弱体化・終了コード固定・例外握り潰し)に"
            "該当する項目は検出されませんでした。"
        )
    else:
        lines.append(f"検出件数: {report.total_findings}件(要確認の合図であり、不正の確定ではない)")
        lines.append("")
        for cr in report.commit_results:
            if not cr.findings:
                continue
            lines.append(f"- コミット {cr.commit_sha[:10]}(「{cr.subject}」):")
            for f in cr.findings:
                lines.append(f"  - [{f.pattern_id}] {f.file_path}: {f.detail}")
    lines.append("")
    lines.append("## 2. AIDD契約遵守の痕跡")
    lines.append("")
    lines.append(report.compliance_trace.detail)
    lines.append("")
    return "\n".join(lines)
