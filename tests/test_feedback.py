from __future__ import annotations

from pathlib import Path

from src.common.settings import AppSettings
from src.input.service import InputPipeline


def test_feedback_injects_issues_into_file_contexts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "password = 'secret123'\n\n"
        "def BadFunction(first, second, third, fourth, fifth, sixth):\n"
        "    return 1\n",
        encoding="utf-8",
    )

    report = InputPipeline(AppSettings()).analyze(str(repo))

    assert report.review_context is not None
    file_context = report.review_context.file_contexts[0]
    assert len(file_context.issues) >= 2
    assert "Hardcoded secret detected" in file_context.suggestions
    assert report.feedback is not None
    assert report.feedback.issue_count_by_file["main.py"] >= 2


def test_feedback_uses_changed_files_as_target_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")

    settings = AppSettings(history_file_path=".history-feedback.json", review_changed_files_only=True)
    first_report = InputPipeline(settings).analyze(str(repo))
    assert first_report.feedback is not None
    assert first_report.feedback.target_file_paths == ["main.py"]

    second_report = InputPipeline(settings).analyze(str(repo))
    assert second_report.feedback is not None
    assert second_report.feedback.target_file_paths == ["main.py"]
    assert second_report.review_context is not None
    assert second_report.review_context.target_file_paths == ["main.py"]


def test_feedback_reports_verification_result(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")

    report = InputPipeline(AppSettings()).analyze(str(repo))

    assert report.feedback is not None
    assert report.feedback.verification_attempts[0].result in {"passed", "failed"}


def test_feedback_reports_only_new_issues_when_enabled(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("password = 'secret123'\n", encoding="utf-8")

    settings = AppSettings(history_file_path=".history-new-issues.json", report_only_new_issues=True)
    first_report = InputPipeline(settings).analyze(str(repo))
    assert len(first_report.issues) >= 1

    second_report = InputPipeline(settings).analyze(str(repo))
    assert second_report.issues == []
    assert second_report.summary is not None
    assert second_report.summary.total_issues == 0
