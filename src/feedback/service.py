from __future__ import annotations

from collections import Counter

from src.common.schemas import (
    FeedbackSummary,
    FileReviewContext,
    HistoricalFingerprint,
    Issue,
    ReportSummary,
    ReviewContext,
    TaskResult,
    VerificationAttempt,
)
from src.common.settings import AppSettings


class CodeReviewFeedbackService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def select_target_files(self, context: ReviewContext) -> list[str]:
        if self.settings.review_changed_files_only and context.incremental_state.new_or_changed_paths:
            return list(context.incremental_state.new_or_changed_paths)
        return [item.path for item in context.file_contexts]

    def inject_issues_into_context(
        self,
        context: ReviewContext,
        issues: list[Issue],
        *,
        include_issue_lists: bool = True,
    ) -> ReviewContext:
        issues_by_path: dict[str, list[Issue]] = {}
        for issue in issues:
            issues_by_path.setdefault(issue.path, []).append(issue)

        updated_contexts: list[FileReviewContext] = []
        for file_context in context.file_contexts:
            updated_contexts.append(
                file_context.model_copy(
                    update={
                        "issues": issues_by_path.get(file_context.path, []) if include_issue_lists else [],
                        "suggestions": [issue.title for issue in issues_by_path.get(file_context.path, [])],
                    }
                )
            )

        return context.model_copy(update={"file_contexts": updated_contexts})

    def filter_new_issues(self, context: ReviewContext, issues: list[Issue]) -> list[Issue]:
        if self.settings.report_only_new_issues is False:
            return issues

        historical_by_path = {
            item.path: set(item.issue_fingerprints)
            for item in context.incremental_state.historical_fingerprints
        }
        filtered: list[Issue] = []
        for issue in issues:
            fingerprint = self._issue_fingerprint(issue)
            if fingerprint not in historical_by_path.get(issue.path, set()):
                filtered.append(issue)
        return filtered

    def build_feedback(
        self,
        context: ReviewContext,
        task_results: list[TaskResult],
        issues: list[Issue],
    ) -> FeedbackSummary:
        issue_count_by_file = Counter(issue.path for issue in issues)
        agent_issue_counts = Counter(task_result.agent_name for task_result in task_results for _ in task_result.issues)
        structure_findings = [
            issue.title for issue in issues if issue.rule_id.startswith("structure.")
        ]
        test_summary = self._build_test_summary(task_results)
        verification_attempts = self._build_verification_attempts(issues)

        return FeedbackSummary(
            target_file_paths=context.target_file_paths,
            issue_count_by_file=dict(sorted(issue_count_by_file.items())),
            agent_issue_counts=dict(sorted(agent_issue_counts.items())),
            structure_findings=structure_findings,
            test_summary=test_summary,
            verification_attempts=verification_attempts,
        )

    def build_summary(self, context: ReviewContext, issues: list[Issue]) -> ReportSummary:
        severity_counts = Counter(issue.severity for issue in issues)
        agent_counts = Counter(issue.rule_id.split(".", 1)[0] for issue in issues)
        return ReportSummary(
            repo_path=context.repo_path,
            total_issues=len(issues),
            total_files_parsed=len(context.file_contexts),
            target_files=context.target_file_paths,
            severity_counts=dict(sorted(severity_counts.items())),
            agent_counts=dict(sorted(agent_counts.items())),
        )

    def _build_test_summary(self, task_results: list[TaskResult]) -> dict[str, str]:
        for task_result in task_results:
            if task_result.agent_name != "test":
                continue
            for evidence in task_result.evidence:
                if evidence.startswith("test-result:"):
                    payload = evidence.split(":", 1)[1]
                    status, _, detail = payload.partition(":")
                    return {"status": status, "detail": detail}
        return {"status": "not_run"}

    def _build_verification_attempts(self, issues: list[Issue]) -> list[VerificationAttempt]:
        if self.settings.self_verification_enabled is False:
            return [
                VerificationAttempt(
                    attempt=1,
                    action="self_verification",
                    result="skipped",
                    detail="self_verification_disabled",
                )
            ]

        if issues:
            return [
                VerificationAttempt(
                    attempt=1,
                    action="review_output_validation",
                    result="failed",
                    detail=f"issues_detected={len(issues)}",
                )
            ]

        return [
            VerificationAttempt(
                attempt=1,
                action="review_output_validation",
                result="passed",
                detail="no_issues_detected",
            )
        ]

    def _issue_fingerprint(self, issue: Issue) -> str:
        return f"{issue.path}:{issue.title.strip().lower()}"
