from __future__ import annotations

import asyncio

from src.agents.base import BaseReviewAgent
from src.agents.performance import PerformanceAgent
from src.agents.security import SecurityAgent
from src.agents.structure import StructureAgent
from src.agents.style import StyleAgent
from src.agents.test import TestAgent
from src.common.schemas import Issue, ReviewContext, ReviewExecution
from src.common.settings import AppSettings
from src.control.plan import CodeReviewPlan, CodeReviewTask
from src.control.scheduler import TaskScheduler
from src.feedback.service import CodeReviewFeedbackService
from src.recovery.service import CodeReviewErrorRecovery


class ReviewExecutionService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.agents = self._build_agents()
        self.recovery = CodeReviewErrorRecovery(settings, list(self.agents))
        self.feedback = CodeReviewFeedbackService(settings)

    def execute(
        self,
        context: ReviewContext,
        *,
        summary_only: bool = False,
    ) -> tuple[ReviewContext, list[Issue], ReviewExecution | None, object | None, object | None, object]:
        plan = self._build_plan(summary_only=summary_only)
        execution = asyncio.run(TaskScheduler(self.agents, self.recovery).run(plan, context))
        issues: list[Issue] = []
        for task_result in execution.task_results:
            issues.extend(task_result.issues)
        issues = self.feedback.filter_new_issues(context, issues)
        updated_context = self.feedback.inject_issues_into_context(
            context,
            issues,
            include_issue_lists=not summary_only,
        )
        feedback_summary = None
        if not summary_only:
            feedback_summary = self.feedback.build_feedback(updated_context, execution.task_results, issues)
        report_summary = self.feedback.build_summary(updated_context, issues)
        recovery_summary = None if summary_only else self.recovery.build_summary()
        execution_result = None if summary_only else execution
        return updated_context, issues, execution_result, recovery_summary, feedback_summary, report_summary

    def _build_plan(self, *, summary_only: bool = False) -> CodeReviewPlan:
        task_order = self.settings.summary_task_order if summary_only else self.settings.review_task_order
        task_dependencies = (
            self.settings.summary_task_dependencies if summary_only else self.settings.review_task_dependencies
        )
        tasks = [
            CodeReviewTask(
                task_id=task_name,
                agent_name=task_name,
                depends_on=list(task_dependencies.get(task_name, [])),
            )
            for task_name in task_order
        ]
        return CodeReviewPlan(tasks)

    def _build_agents(self) -> dict[str, BaseReviewAgent]:
        return {
            "structure": StructureAgent(
                max_function_lines=self.settings.structure_max_function_lines,
                max_branch_nodes=self.settings.structure_max_branch_nodes,
            ),
            "security": SecurityAgent(),
            "style": StyleAgent(
                max_function_lines=self.settings.style_max_function_lines,
                max_parameters=self.settings.style_max_parameters,
            ),
            "performance": PerformanceAgent(),
            "test": TestAgent(
                test_command=self.settings.test_command,
                timeout_seconds=self.settings.test_timeout_seconds,
                execution_enabled=self.settings.test_execution_enabled,
            ),
        }
