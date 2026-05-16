from __future__ import annotations

import re

from src.agents.base import BaseReviewAgent
from src.common.schemas import AgentReport, Issue, ReviewContext


SNAKE_CASE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
PASCAL_CASE_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]+$")


class StyleAgent(BaseReviewAgent):
    agent_name = "style"

    def __init__(self, max_function_lines: int = 30, max_parameters: int = 5) -> None:
        self.max_function_lines = max_function_lines
        self.max_parameters = max_parameters

    def run(self, context: ReviewContext) -> AgentReport:
        issues: list[Issue] = []
        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue

            for function in file_context.functions:
                if not SNAKE_CASE_PATTERN.match(function.name):
                    issues.append(
                        Issue(
                            rule_id="style.function-name",
                            title="Function name should use snake_case",
                            description="Python function names should follow snake_case for consistency.",
                            severity="low",
                            path=file_context.path,
                            line=function.line_start,
                            confidence=0.95,
                            evidence=[function.name],
                        )
                    )

                function_length = function.line_end - function.line_start + 1
                if function_length > self.max_function_lines:
                    issues.append(
                        Issue(
                            rule_id="style.function-length",
                            title="Function is longer than style threshold",
                            description="Function length exceeds the configured style threshold.",
                            severity="low",
                            path=file_context.path,
                            line=function.line_start,
                            confidence=0.95,
                            evidence=[f"function={function.name}", f"line_span={function_length}"],
                        )
                    )

                if function.parameter_count is not None and function.parameter_count > self.max_parameters:
                    issues.append(
                        Issue(
                            rule_id="style.too-many-parameters",
                            title="Function has too many parameters",
                            description="Function signature exceeds the preferred parameter count.",
                            severity="low",
                            path=file_context.path,
                            line=function.line_start,
                            confidence=0.95,
                            evidence=[f"function={function.name}", f"parameter_count={function.parameter_count}"],
                        )
                    )

            for class_symbol in file_context.classes:
                if not PASCAL_CASE_PATTERN.match(class_symbol.name):
                    issues.append(
                        Issue(
                            rule_id="style.class-name",
                            title="Class name should use PascalCase",
                            description="Python class names should follow PascalCase.",
                            severity="low",
                            path=file_context.path,
                            line=class_symbol.line_start,
                            confidence=0.95,
                            evidence=[class_symbol.name],
                        )
                    )

        return AgentReport(
            agent_name=self.agent_name,
            issues=issues,
            evidence=[f"highlighted_paths={len(context.structure_summary.highlighted_paths)}"],
            severity="info" if not issues else "low",
        )
