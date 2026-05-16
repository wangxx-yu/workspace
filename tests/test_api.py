from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import create_app
from src.common.settings import AppSettings


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_endpoint_returns_report_contract() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post("/analyze", json={"repo_ref": "tests/fixtures/python_sample_repo"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["total_files_parsed"] == 4
    assert "review_context" in payload
    assert "execution" in payload
    assert "recovery" in payload
    assert "feedback" in payload


def test_analyze_endpoint_accepts_runtime_overrides() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "review_changed_files_only": False,
            "test_execution_enabled": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_context"]["target_file_paths"] == [
        "app/__init__.py",
        "app/helpers.py",
        "app/service.py",
        "main.py",
    ]


def test_analyze_endpoint_accepts_file_git_url(tmp_path) -> None:
    import git

    source_repo = tmp_path / "source"
    source_repo.mkdir()
    (source_repo / "main.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    repo = git.Repo.init(source_repo)
    repo.index.add(["main.py"])
    repo.index.commit("init")

    client = TestClient(create_app(AppSettings(temp_repo_parent_dir=str(tmp_path))))
    response = client.post("/analyze", json={"repo_ref": source_repo.as_uri()})

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["total_files_parsed"] == 1


def test_analyze_endpoint_filters_issues_by_severity_and_agent() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "severity_filter": ["low"],
            "agent_filter": ["test"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert all(issue["severity"] == "low" for issue in payload["issues"])
    assert all(issue["rule_id"].startswith("test.") for issue in payload["issues"])


def test_analyze_formatted_endpoint_returns_sarif() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post(
        "/analyze-formatted",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "output_format": "sarif",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "sarif"
    assert "\"version\": \"2.1.0\"" in payload["content"]


def test_analyze_summary_endpoint_returns_lightweight_summary() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post(
        "/analyze-summary",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "severity_filter": ["low"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repo_path"].endswith("python_sample_repo")
    assert "severity_counts" in payload
    assert "agent_counts" in payload
    assert "metrics" in payload


def test_analyze_summary_endpoint_applies_filters_and_pagination() -> None:
    client = TestClient(create_app(AppSettings(report_only_new_issues=False)))

    response = client.post(
        "/analyze-summary",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "severity_filter": ["low"],
            "sort_by": "path",
            "offset": 1,
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_issues"] == 2
    assert payload["severity_counts"] == {"low": 2}


def test_analyze_summary_endpoint_uses_lightweight_agent_set() -> None:
    client = TestClient(create_app(AppSettings(report_only_new_issues=False)))

    response = client.post(
        "/analyze-summary",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["agent_counts"]).issubset({"structure", "security", "test"})
    assert payload["metrics"]["executed_agents"] == ["structure", "security", "test"]


def test_analyze_endpoint_supports_sorting_and_pagination() -> None:
    client = TestClient(create_app(AppSettings(report_only_new_issues=False)))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "sort_by": "path",
            "offset": 1,
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["issues"]) == 2
    sorted_paths = [issue["path"] for issue in payload["issues"]]
    assert sorted_paths == sorted(sorted_paths)


def test_analyze_endpoint_supports_path_filter() -> None:
    client = TestClient(create_app(AppSettings(report_only_new_issues=False)))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "path_filter": ["app/service.py"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert all(issue["path"] == "app/service.py" for issue in payload["issues"])


def test_analyze_endpoint_supports_payload_trimming() -> None:
    client = TestClient(create_app(AppSettings(report_only_new_issues=False)))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "include_parsed_files": False,
            "include_project_graph": False,
            "include_review_context": False,
            "include_execution": False,
            "include_feedback": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed_files"] == []
    assert payload["project_graph"] == {"nodes": [], "edges": []}
    assert payload["review_context"] is None
    assert payload["execution"] is None
    assert payload["feedback"] is None


def test_analyze_endpoint_returns_clone_error_category(tmp_path, monkeypatch) -> None:
    import subprocess

    def failed_clone(*args, **kwargs):
        return subprocess.CompletedProcess(args=["git", "clone"], returncode=128, stderr="fatal: repository not found")

    monkeypatch.setattr(subprocess, "run", failed_clone)
    client = TestClient(create_app(AppSettings(temp_repo_parent_dir=str(tmp_path))))

    response = client.post(
        "/analyze",
        json={"repo_ref": "https://github.com/example/missing"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "repo_clone_failed"
    assert payload["error"]["details"]["category"] == "repository_not_found"


def test_analyze_endpoint_rejects_invalid_sort_by() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "sort_by": "created_at",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"


def test_analyze_endpoint_rejects_negative_offset() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "offset": -1,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"


def test_analyze_endpoint_rejects_non_positive_limit() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.post(
        "/analyze",
        json={
            "repo_ref": "tests/fixtures/python_sample_repo",
            "limit": 0,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"


def test_openapi_exposes_error_responses_and_summary_request_model() -> None:
    client = TestClient(create_app(AppSettings()))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    analyze_operation = payload["paths"]["/analyze"]["post"]
    summary_operation = payload["paths"]["/analyze-summary"]["post"]
    analyze_schema_ref = analyze_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    summary_schema_ref = summary_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]

    assert analyze_operation["responses"]["400"]["content"]["application/json"]["example"]["error"]["code"] == "repo_clone_failed"
    assert analyze_operation["responses"]["422"]["content"]["application/json"]["example"]["error"]["code"] == "validation_error"
    assert analyze_schema_ref.endswith("AnalyzeRequest")
    assert summary_schema_ref.endswith("AnalyzeSummaryRequest")


def test_analyze_summary_endpoint_uses_pipeline_summary_mode(monkeypatch) -> None:
    from src.common.schemas import ProjectGraph, Report, ReportMetadata, ReportSummary, ReviewContext

    captured: dict[str, bool] = {}

    def fake_analyze(self, repo_ref: str, *, summary_only: bool = False):
        captured["summary_only"] = summary_only
        return Report(
            parsed_files=[],
            project_graph=ProjectGraph(nodes=[], edges=[]),
            failed_files=[],
            issues=[],
            metadata=ReportMetadata(repo_path=repo_ref, total_files_scanned=0, total_files_parsed=0, total_failed_files=0),
            review_context=ReviewContext.model_validate(
                {
                    "repo_path": repo_ref,
                    "file_contexts": [],
                    "target_file_paths": [],
                    "structure_summary": {"total_files": 0, "language_distribution": {}, "highlighted_paths": []},
                    "key_files": [],
                    "dependency_focus_paths": [],
                    "incremental_state": {"changed_files": [], "unchanged_files": [], "new_or_changed_paths": [], "historical_fingerprints": []},
                    "budget": {
                        "tokenizer_name": "simple-char-budget",
                        "estimated_tokens": 0,
                        "structure_summary_cap": 0,
                        "key_files_token_cap": 0,
                        "dependency_token_cap": 0,
                        "per_file_issue_budget": 0,
                        "within_budget": True,
                        "truncation_reason": None,
                    },
                }
            ),
            execution=None,
            recovery=None,
            feedback=None,
            summary=ReportSummary(repo_path=repo_ref, total_issues=0, total_files_parsed=0),
        )

    monkeypatch.setattr("src.api.InputPipeline.analyze", fake_analyze)
    client = TestClient(create_app(AppSettings()))

    response = client.post("/analyze-summary", json={"repo_ref": "tests/fixtures/python_sample_repo"})

    assert response.status_code == 200
    assert captured["summary_only"] is True
