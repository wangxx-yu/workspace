from __future__ import annotations

import shutil
from pathlib import Path

from src.common.settings import AppSettings
from src.input.repo_loader import RepoCloneError, RepoLoader
from src.input.service import InputPipeline


FIXTURE_PATH = Path("tests/fixtures/python_sample_repo")


def test_input_pipeline_builds_parsed_files_and_dependency_graph() -> None:
    isolated_repo = Path("tests/tmp/python_sample_repo")
    if isolated_repo.exists():
        shutil.rmtree(isolated_repo)
    shutil.copytree(FIXTURE_PATH, isolated_repo, ignore=shutil.ignore_patterns(".code-review-history.json"))

    report = InputPipeline(AppSettings()).analyze(str(isolated_repo))

    assert report.metadata.total_files_parsed == 4
    assert len(report.failed_files) == 0

    parsed_by_path = {item.path: item for item in report.parsed_files}
    assert "main.py" in parsed_by_path
    assert "app/service.py" in parsed_by_path

    main_file = parsed_by_path["main.py"]
    assert main_file.language == "python"
    assert main_file.parse_mode == "ast"
    assert main_file.imports == ["app.service"]

    edges = {(edge.source, edge.target, edge.resolved) for edge in report.project_graph.edges}
    assert ("main.py", "app/service.py", True) in edges
    assert ("app/service.py", "app/helpers.py", True) in edges
    assert report.review_context is not None
    assert report.review_context.structure_summary.total_files == 4
    assert report.review_context.incremental_state.changed_files == [
        "app/__init__.py",
        "app/helpers.py",
        "app/service.py",
        "main.py",
    ]
    assert report.review_context.key_files[0].path == "main.py"
    assert report.review_context.budget.within_budget is True
    assert report.execution is not None
    assert report.execution.completed_order == ["structure", "performance", "security", "style", "test"]
    assert report.execution.failed_tasks == []

    shutil.rmtree(isolated_repo)


def test_input_pipeline_isolates_parse_failures(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "good.py").write_text("def ok() -> int:\n    return 1\n", encoding="utf-8")
    (repo / "bad.py").write_text("def broken(:\n    return 1\n", encoding="utf-8")

    report = InputPipeline(AppSettings()).analyze(str(repo))

    assert report.metadata.total_files_parsed == 1
    assert len(report.failed_files) == 1
    assert report.failed_files[0].path == "bad.py"
    assert report.failed_files[0].stage == "parse"
    assert report.parsed_files[0].path == "good.py"


def test_input_pipeline_uses_history_for_incremental_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")

    settings = AppSettings(history_file_path=".history.json")
    first_report = InputPipeline(settings).analyze(str(repo))
    assert first_report.review_context is not None
    assert first_report.review_context.incremental_state.changed_files == ["main.py"]

    second_report = InputPipeline(settings).analyze(str(repo))
    assert second_report.review_context is not None
    assert second_report.review_context.incremental_state.changed_files == []
    assert second_report.review_context.incremental_state.unchanged_files == ["main.py"]
    assert second_report.failed_files == []


def test_repo_loader_supports_file_git_url(tmp_path: Path) -> None:
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    (source_repo / "main.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")

    import git

    repo = git.Repo.init(source_repo)
    repo.index.add(["main.py"])
    repo.index.commit("init")

    settings = AppSettings(temp_repo_parent_dir=str(tmp_path))
    loaded_repo = RepoLoader(settings).load(source_repo.as_uri())
    try:
        assert loaded_repo.path.exists()
        assert (loaded_repo.path / "main.py").exists()
        assert loaded_repo.cleanup_path is not None
    finally:
        cleanup_path = loaded_repo.cleanup_path
        loaded_repo.cleanup()
        assert cleanup_path is not None
        assert cleanup_path.exists() is False


def test_repo_loader_normalizes_github_https_url(tmp_path: Path, monkeypatch) -> None:
    settings = AppSettings(temp_repo_parent_dir=str(tmp_path))
    loader = RepoLoader(settings)
    captured: dict[str, str] = {}

    def fake_clone(repo_ref: str):
        captured["repo_ref"] = repo_ref
        return loader._load_local("tests/fixtures/python_sample_repo")

    monkeypatch.setattr(loader, "_clone_remote", fake_clone)

    loaded_repo = loader.load("https://github.com/example/project")

    assert loaded_repo.path.exists()
    assert captured["repo_ref"] == "https://github.com/example/project.git"


def test_repo_loader_reports_clone_timeout(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git clone", timeout=1)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    settings = AppSettings(temp_repo_parent_dir=str(tmp_path), git_clone_timeout_seconds=1)

    try:
        RepoLoader(settings).load("file:///tmp/nonexistent-repo")
    except TimeoutError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("expected TimeoutError")


def test_repo_loader_classifies_repository_not_found(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    def failed_clone(*args, **kwargs):
        return subprocess.CompletedProcess(args=["git", "clone"], returncode=128, stderr="fatal: repository not found")

    monkeypatch.setattr(subprocess, "run", failed_clone)
    settings = AppSettings(temp_repo_parent_dir=str(tmp_path))

    try:
        RepoLoader(settings).load("https://github.com/example/missing")
    except RepoCloneError as exc:
        assert exc.category == "repository_not_found"
    else:
        raise AssertionError("expected RepoCloneError")


def test_repo_loader_classifies_permission_denied(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    def failed_clone(*args, **kwargs):
        return subprocess.CompletedProcess(args=["git", "clone"], returncode=128, stderr="fatal: Authentication failed")

    monkeypatch.setattr(subprocess, "run", failed_clone)
    settings = AppSettings(temp_repo_parent_dir=str(tmp_path))

    try:
        RepoLoader(settings).load("https://github.com/example/private")
    except RepoCloneError as exc:
        assert exc.category == "permission_denied"
    else:
        raise AssertionError("expected RepoCloneError")


def test_input_pipeline_summary_mode_trims_heavy_fields() -> None:
    report = InputPipeline(AppSettings(report_only_new_issues=False)).analyze(
        "tests/fixtures/python_sample_repo",
        summary_only=True,
    )

    assert report.parsed_files == []
    assert report.project_graph.nodes == []
    assert report.review_context is None
    assert report.execution is None
    assert report.recovery is None
    assert report.feedback is None
    assert report.summary is not None


def test_input_pipeline_compresses_history_context_for_summary_mode(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    from src.context.manager import CodeReviewContextManager

    original_persist_history = CodeReviewContextManager.persist_history

    def capture_persist_history(self, review_context):
        captured["review_context"] = review_context
        return original_persist_history(self, review_context)

    monkeypatch.setattr(CodeReviewContextManager, "persist_history", capture_persist_history)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("password = 'secret123'\n", encoding="utf-8")

    report = InputPipeline(AppSettings(report_only_new_issues=False)).analyze(str(repo), summary_only=True)
    persisted_context = captured["review_context"]

    assert report.summary is not None
    assert persisted_context.file_contexts[0].functions == []
    assert persisted_context.file_contexts[0].classes == []
    assert persisted_context.file_contexts[0].dependencies == []
    assert persisted_context.file_contexts[0].suggestions != []


def test_context_manager_summary_mode_reduces_summary_fields(tmp_path: Path) -> None:
    from src.context.manager import CodeReviewContextManager
    from src.input.dependency_extractor import DependencyExtractor
    from src.input.parser import CodeParser
    from src.input.scanner import RepositoryScanner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("from helper import run\nrun()\n", encoding="utf-8")
    (repo / "helper.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    settings = AppSettings(report_only_new_issues=False)
    scanner = RepositoryScanner(settings)
    parser = CodeParser()
    scanned_files, _ = scanner.scan(repo)
    parsed_files = [parser.parse(item) for item in scanned_files]
    graph = DependencyExtractor().build_graph(parsed_files)

    full_context = CodeReviewContextManager(settings, repo).build(parsed_files, graph, summary_only=False)
    summary_context = CodeReviewContextManager(settings, repo).build(parsed_files, graph, summary_only=True)

    assert full_context.key_files != []
    assert full_context.structure_summary.highlighted_paths != []
    assert summary_context.key_files == []
    assert summary_context.dependency_focus_paths == []
    assert summary_context.structure_summary.highlighted_paths == []
