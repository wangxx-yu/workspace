from __future__ import annotations

from src.common.settings import AppSettings
from src.input.service import InputPipeline
from src.report_processing import ReportQueryOptions, build_filtered_summary, filter_report, trim_report


def test_report_processing_filters_trims_and_builds_summary() -> None:
    report = InputPipeline(AppSettings(report_only_new_issues=False)).analyze("tests/fixtures/python_sample_repo")
    options = ReportQueryOptions(
        severity_filter=["low"],
        path_filter=["app/service.py"],
        include_parsed_files=False,
        include_project_graph=False,
    )

    filtered = filter_report(report, options)
    trimmed = trim_report(filtered, options)
    summary = build_filtered_summary(filtered, AppSettings(report_only_new_issues=False), options)

    assert all(issue.severity == "low" for issue in filtered.issues)
    assert all(issue.path == "app/service.py" for issue in filtered.issues)
    assert trimmed.parsed_files == []
    assert trimmed.project_graph.nodes == []
    assert summary.repo_path.endswith("python_sample_repo")


def test_report_processing_builds_summary_without_review_context() -> None:
    report = InputPipeline(AppSettings(report_only_new_issues=False)).analyze(
        "tests/fixtures/python_sample_repo",
        summary_only=True,
    )
    options = ReportQueryOptions(severity_filter=["low"])

    summary = build_filtered_summary(report, AppSettings(report_only_new_issues=False), options)

    assert report.review_context is None
    assert summary.repo_path.endswith("python_sample_repo")
    assert summary.total_files_parsed == 4


def test_report_processing_preserves_metrics_when_rebuilding_summary() -> None:
    report = InputPipeline(AppSettings(report_only_new_issues=False)).analyze("tests/fixtures/python_sample_repo")
    options = ReportQueryOptions(severity_filter=["low"])

    summary = build_filtered_summary(report, AppSettings(report_only_new_issues=False), options)

    assert summary.metrics == report.summary.metrics
