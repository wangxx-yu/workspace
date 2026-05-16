from __future__ import annotations

import json
from pathlib import Path

from src.common.settings import AppSettings
from src.input.service import InputPipeline
from src.output.formatter import ReportFormatter


def test_sarif_output_contains_runs_and_results(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("password = 'secret123'\n", encoding="utf-8")

    report = InputPipeline(AppSettings()).analyze(str(repo))

    payload = json.loads(ReportFormatter().to_sarif(report))

    assert payload["version"] == "2.1.0"
    assert len(payload["runs"]) == 1
    assert "results" in payload["runs"][0]
    assert "helpUri" in payload["runs"][0]["tool"]["driver"]["rules"][0]
    assert "properties" in payload["runs"][0]["results"][0]
