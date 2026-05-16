from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.common.schemas import Report, ReportSummary
from src.common.settings import AppSettings
from src.feedback.service import CodeReviewFeedbackService


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass(slots=True)
class ReportQueryOptions:
    severity_filter: list[str] | None = None
    agent_filter: list[str] | None = None
    path_filter: list[str] | None = None
    sort_by: Literal["severity", "path"] | None = None
    offset: int | None = None
    limit: int | None = None
    include_parsed_files: bool = True
    include_project_graph: bool = True
    include_review_context: bool = True
    include_execution: bool = True
    include_feedback: bool = True


def filter_report(report: Report, options: ReportQueryOptions) -> Report:
    filtered_issues = list(report.issues)
    if options.severity_filter:
        allowed = set(options.severity_filter)
        filtered_issues = [issue for issue in filtered_issues if issue.severity in allowed]
    if options.agent_filter:
        allowed_agents = set(options.agent_filter)
        filtered_issues = [issue for issue in filtered_issues if issue.rule_id.split(".", 1)[0] in allowed_agents]
    if options.path_filter:
        allowed_paths = set(options.path_filter)
        filtered_issues = [issue for issue in filtered_issues if issue.path in allowed_paths]
    if options.sort_by == "severity":
        filtered_issues.sort(key=lambda issue: (SEVERITY_ORDER[issue.severity], issue.path, issue.line or 0))
    elif options.sort_by == "path":
        filtered_issues.sort(key=lambda issue: (issue.path, issue.line or 0, issue.rule_id))
    start = options.offset or 0
    end = None if options.limit is None else start + options.limit
    filtered_issues = filtered_issues[start:end]
    return report.model_copy(update={"issues": filtered_issues})


def trim_report(report: Report, options: ReportQueryOptions) -> Report:
    updates = {}
    if not options.include_parsed_files:
        updates["parsed_files"] = []
    if not options.include_project_graph:
        updates["project_graph"] = report.project_graph.model_copy(update={"nodes": [], "edges": []})
    if not options.include_review_context:
        updates["review_context"] = None
    if not options.include_execution:
        updates["execution"] = None
    if not options.include_feedback:
        updates["feedback"] = None
    if not updates:
        return report
    return report.model_copy(update=updates)


def build_filtered_summary(report: Report, settings: AppSettings, options: ReportQueryOptions) -> ReportSummary:
    filtered_report = filter_report(report, options)
    if report.review_context is not None:
        summary = CodeReviewFeedbackService(settings).build_summary(report.review_context, filtered_report.issues)
        if report.summary is not None:
            return summary.model_copy(update={"metrics": report.summary.metrics})
        return summary
    if report.summary is not None:
        severity_counts: dict[str, int] = {}
        agent_counts: dict[str, int] = {}
        for issue in filtered_report.issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            agent_name = issue.rule_id.split(".", 1)[0]
            agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1
        return ReportSummary(
            repo_path=report.summary.repo_path,
            total_issues=len(filtered_report.issues),
            total_files_parsed=report.summary.total_files_parsed,
            target_files=report.summary.target_files,
            severity_counts=dict(sorted(severity_counts.items())),
            agent_counts=dict(sorted(agent_counts.items())),
            metrics=report.summary.metrics,
        )
    raise ValueError("report summary is unavailable")
