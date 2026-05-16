from __future__ import annotations

import ast

from src.agents.base import BaseReviewAgent
from src.common.schemas import AgentReport, Issue, ReviewContext


class PerformanceAgent(BaseReviewAgent):
    agent_name = "performance"

    def run(self, context: ReviewContext) -> AgentReport:
        issues: list[Issue] = []
        issues.extend(self._detect_loop_io(context))
        issues.extend(self._detect_repeated_len_calls(context))
        if context.budget.within_budget is False:
            issues.append(
                Issue(
                    rule_id="performance.context-budget",
                    title="Context budget exceeded",
                    description="Context estimation exceeded the configured budget and may degrade review quality.",
                    severity="medium",
                    path=context.file_contexts[0].path if context.file_contexts else ".",
                    confidence=0.9,
                    evidence=[context.budget.truncation_reason or "budget_exceeded"],
                )
            )

        return AgentReport(
            agent_name=self.agent_name,
            issues=issues,
            evidence=[f"estimated_tokens={context.budget.estimated_tokens}"],
            severity="info" if not issues else "medium",
        )

    def _detect_loop_io(self, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue
            tree = self._parse_python_ast(context, file_context)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.For, ast.While)):
                    continue
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = self._call_name(child.func)
                        if func_name in {"open", "requests.get", "requests.post"}:
                            issues.append(
                                Issue(
                                    rule_id="performance.loop-io",
                                    title="I/O call inside loop",
                                    description="Repeated I/O inside a loop may cause avoidable latency.",
                                    severity="medium",
                                    path=file_context.path,
                                    line=getattr(child, "lineno", None),
                                    confidence=0.85,
                                    evidence=[func_name],
                                )
                            )
        return issues

    def _detect_repeated_len_calls(self, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for file_context in context.file_contexts:
            if file_context.language != "python":
                continue
            tree = self._parse_python_ast(context, file_context)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.For, ast.While)):
                    continue
                len_calls = [
                    child
                    for child in ast.walk(node)
                    if isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "len"
                ]
                if len(len_calls) >= 2:
                    issues.append(
                        Issue(
                            rule_id="performance.repeated-len-call",
                            title="Repeated len() call inside loop",
                            description="Repeated length calculation inside a loop may be cached for clarity and efficiency.",
                            severity="low",
                            path=file_context.path,
                            line=getattr(len_calls[0], "lineno", None),
                            confidence=0.8,
                            evidence=[f"len_calls={len(len_calls)}"],
                        )
                    )
        return issues

    def _call_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base_name = self._call_name(node.value)
            if base_name is None:
                return node.attr
            return f"{base_name}.{node.attr}"
        return None
