from __future__ import annotations

import json

from src.common.schemas import Report
from src.output.sarif import SarifFormatter


class ReportFormatter:
    def to_json(self, report: Report) -> str:
        return report.model_dump_json(indent=2)

    def to_sarif(self, report: Report) -> str:
        return json.dumps(SarifFormatter().to_sarif(report), indent=2)

    def to_markdown(self, report: Report) -> str:
        lines = [
            "# Code Review Report",
            "",
            f"- Repo: `{report.metadata.repo_path}`",
            f"- Parsed files: `{report.metadata.total_files_parsed}`",
            f"- Failed files: `{report.metadata.total_failed_files}`",
            "",
            "## Parsed Files",
            "",
        ]

        for item in report.parsed_files:
            lines.append(f"- `{item.path}` ({item.language}, {item.parse_mode})")

        lines.extend(["", "## Dependency Edges", ""])
        for edge in report.project_graph.edges:
            lines.append(
                f"- `{edge.source}` -> `{edge.target}` confidence={edge.resolution_confidence:.1f}"
            )

        if report.review_context is not None:
            lines.extend(["", "## Review Context", ""])
            lines.append(f"- Total files: `{report.review_context.structure_summary.total_files}`")
            lines.append(f"- Key files: `{len(report.review_context.key_files)}`")
            lines.append(
                f"- Changed files: `{len(report.review_context.incremental_state.changed_files)}`"
            )
            lines.append(
                f"- Estimated tokens: `{report.review_context.budget.estimated_tokens}`"
            )

        if report.execution is not None:
            lines.extend(["", "## Execution", ""])
            lines.append(f"- Progress: `{report.execution.progress:.2f}`")
            lines.append(f"- Completed tasks: `{', '.join(report.execution.completed_order)}`")
            lines.append(f"- Failed tasks: `{', '.join(report.execution.failed_tasks)}`")

        if report.recovery is not None:
            lines.extend(["", "## Recovery", ""])
            lines.append(f"- Requested mode: `{report.recovery.mode_requested}`")
            lines.append(f"- Effective mode: `{report.recovery.mode_effective}`")
            lines.append(f"- Recovery events: `{len(report.recovery.events)}`")

        if report.feedback is not None:
            lines.extend(["", "## Feedback", ""])
            lines.append(f"- Target files: `{', '.join(report.feedback.target_file_paths)}`")
            lines.append(f"- Verification attempts: `{len(report.feedback.verification_attempts)}`")

        if report.issues:
            lines.extend(["", "## Issues", ""])
            for issue in report.issues:
                lines.append(f"- `{issue.rule_id}` {issue.severity} `{issue.path}` {issue.title}")

        if report.failed_files:
            lines.extend(["", "## Failed Files", ""])
            for item in report.failed_files:
                lines.append(f"- `{item.path}` [{item.stage}] {item.reason}")

        return "\n".join(lines)
