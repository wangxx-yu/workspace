from __future__ import annotations

import subprocess
from pathlib import Path

from src.agents.base import BaseReviewAgent
from src.common.schemas import AgentReport, Issue, ReviewContext


TEST_RESULT_PREFIX = "test-result:"


class TestAgent(BaseReviewAgent):
    agent_name = "test"

    def __init__(self, test_command: str = "pytest", timeout_seconds: int = 20, execution_enabled: bool = False) -> None:
        self.test_command = test_command
        self.timeout_seconds = timeout_seconds
        self.execution_enabled = execution_enabled

    def run(self, context: ReviewContext) -> AgentReport:
        issues: list[Issue] = []
        test_files = [item.path for item in context.file_contexts if self._is_test_file(item.path)]
        has_test_file = bool(test_files)
        evidence = [f"has_test_file={has_test_file}", f"test_files={len(test_files)}"]

        target_files = [
            item for item in context.file_contexts if item.path in context.target_file_paths and not self._is_test_file(item.path)
        ]

        if not has_test_file:
            issues.append(
                Issue(
                    rule_id="test.no-tests-detected",
                    title="No tests detected in review scope",
                    description="The current review scope does not include obvious test files.",
                    severity="low",
                    path=context.file_contexts[0].path if context.file_contexts else ".",
                    confidence=0.7,
                    evidence=["heuristic=test-file-name-scan"],
                )
            )

        for file_context in target_files:
            if file_context.path == "__init__.py" or file_context.path.endswith("/__init__.py"):
                continue
            expected_test_names = self._expected_test_names(file_context.path)
            mapped = [test_path for test_path in test_files if Path(test_path).name in expected_test_names]
            if not mapped:
                issues.append(
                    Issue(
                        rule_id="test.missing-targeted-test",
                        title="No targeted test file mapped",
                        description="The changed source file has no obvious matching test file by naming convention.",
                        severity="low",
                        path=file_context.path,
                        confidence=0.7,
                        evidence=[f"expected_tests={','.join(expected_test_names)}"],
                        )
                )

        evidence.extend(self._run_tests_if_enabled(context))

        return AgentReport(
            agent_name=self.agent_name,
            issues=issues,
            evidence=evidence,
            severity="info" if not issues else "low",
        )

    def _is_test_file(self, path: str) -> bool:
        return path.startswith("tests/") or path.startswith("test_") or "/test_" in path

    def _expected_test_names(self, path: str) -> list[str]:
        file_name = Path(path).stem
        parent_name = Path(path).parent.name
        names = [f"test_{file_name}.py", f"{file_name}_test.py"]
        if parent_name and parent_name != ".":
            names.append(f"test_{parent_name}_{file_name}.py")
        return names

    def _run_tests_if_enabled(self, context: ReviewContext) -> list[str]:
        if self.execution_enabled is False:
            return [f"{TEST_RESULT_PREFIX}skipped:execution_disabled"]

        try:
            completed = subprocess.run(
                self.test_command.split(),
                cwd=context.repo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return [f"{TEST_RESULT_PREFIX}failed:timeout"]
        except FileNotFoundError:
            return [f"{TEST_RESULT_PREFIX}skipped:command_not_found"]

        if completed.returncode == 0:
            return [f"{TEST_RESULT_PREFIX}passed:returncode=0"]
        return [f"{TEST_RESULT_PREFIX}failed:returncode={completed.returncode}"]
