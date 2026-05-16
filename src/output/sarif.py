from __future__ import annotations

from src.common.schemas import Issue, Report


SEVERITY_LEVEL_MAP = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
}


class SarifFormatter:
    def to_sarif(self, report: Report) -> dict:
        rules = self._build_rules(report.issues)
        results = [self._build_result(issue) for issue in report.issues]
        return {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "CodeReviewAgent",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }

    def _build_rules(self, issues: list[Issue]) -> list[dict]:
        unique_rules: dict[str, dict] = {}
        for issue in issues:
            unique_rules.setdefault(
                issue.rule_id,
                {
                    "id": issue.rule_id,
                    "name": issue.title,
                    "shortDescription": {"text": issue.title},
                    "fullDescription": {"text": issue.description},
                    "helpUri": f"https://example.com/rules/{issue.rule_id}",
                    "properties": {"severity": issue.severity},
                },
            )
        return list(unique_rules.values())

    def _build_result(self, issue: Issue) -> dict:
        level = SEVERITY_LEVEL_MAP[issue.severity]
        region: dict[str, int] = {}
        if issue.line is not None:
            region["startLine"] = issue.line

        return {
            "ruleId": issue.rule_id,
            "level": level,
            "message": {"text": issue.title},
            "properties": {
                "confidence": issue.confidence,
                "severity": issue.severity,
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": issue.path},
                        "region": region,
                    }
                }
            ],
        }
