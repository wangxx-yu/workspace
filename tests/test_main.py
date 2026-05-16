from __future__ import annotations

import json

from main import main


def test_main_analyze_outputs_json(capsys) -> None:
    exit_code = main([
        "analyze",
        "--repo",
        "tests/fixtures/python_sample_repo",
        "--format",
        "json",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["metadata"]["total_files_parsed"] == 4
    assert payload["review_context"]["structure_summary"]["total_files"] == 4
    assert payload["review_context"]["budget"]["within_budget"] is True
    assert payload["execution"]["completed_order"] == ["structure", "performance", "security", "style", "test"]
    assert payload["recovery"]["mode_effective"] == "analyze_only"


def test_main_analyze_outputs_sarif(capsys) -> None:
    exit_code = main([
        "analyze",
        "--repo",
        "tests/fixtures/python_sample_repo",
        "--format",
        "sarif",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["version"] == "2.1.0"


def test_main_analyze_accepts_runtime_overrides(capsys) -> None:
    exit_code = main([
        "analyze",
        "--repo",
        "tests/fixtures/python_sample_repo",
        "--format",
        "json",
        "--review-changed-files-only",
        "false",
        "--test-execution-enabled",
        "false",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["review_context"]["target_file_paths"] == [
        "app/__init__.py",
        "app/helpers.py",
        "app/service.py",
        "main.py",
    ]


def test_main_analyze_supports_filters_and_pagination(capsys) -> None:
    exit_code = main([
        "analyze",
        "--repo",
        "tests/fixtures/python_sample_repo",
        "--format",
        "json",
        "--sort-by",
        "path",
        "--offset",
        "1",
        "--limit",
        "2",
        "--severity-filter",
        "low",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert len(payload["issues"]) <= 2


def test_main_analyze_supports_summary_output(capsys) -> None:
    exit_code = main([
        "analyze",
        "--repo",
        "tests/fixtures/python_sample_repo",
        "--summary",
        "--severity-filter",
        "low",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "total_issues" in payload
    assert "severity_counts" in payload
    assert "metrics" in payload
    assert payload["metrics"]["executed_agents"] == ["structure", "security", "test"]
