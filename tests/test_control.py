from __future__ import annotations

import asyncio

from src.agents.base import BaseReviewAgent
from src.common.schemas import AgentReport, ReviewContext
from src.common.settings import AppSettings
from src.context.manager import CodeReviewContextManager
from src.control.service import ReviewExecutionService
from src.control.plan import CodeReviewPlan, CodeReviewTask
from src.control.scheduler import TaskScheduler
from src.input.dependency_extractor import DependencyExtractor
from src.input.parser import CodeParser
from src.input.repo_loader import RepoLoader
from src.input.scanner import RepositoryScanner
from src.recovery.service import CodeReviewErrorRecovery


class RecordingAgent(BaseReviewAgent):
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def run(self, context: ReviewContext) -> AgentReport:
        return AgentReport(agent_name=self.agent_name, evidence=[str(len(context.file_contexts))])


class FailingAgent(BaseReviewAgent):
    agent_name = "security"

    def run(self, context: ReviewContext) -> AgentReport:
        raise RuntimeError("boom")


def _build_context() -> ReviewContext:
    settings = AppSettings(history_file_path=".history-test.json")
    loaded_repo = RepoLoader(settings).load("tests/fixtures/python_sample_repo")
    repo_path = loaded_repo.path
    scanned_files, _ = RepositoryScanner(settings).scan(repo_path)
    parsed_files = [CodeParser().parse(item) for item in scanned_files]
    graph = DependencyExtractor().build_graph(parsed_files)
    return CodeReviewContextManager(settings, repo_path).build(parsed_files, graph)


def test_code_review_plan_orders_tasks_by_dependencies() -> None:
    plan = CodeReviewPlan(
        [
            CodeReviewTask(task_id="structure", agent_name="structure"),
            CodeReviewTask(task_id="security", agent_name="security", depends_on=["structure"]),
            CodeReviewTask(task_id="style", agent_name="style", depends_on=["structure"]),
        ]
    )

    assert [task.task_id for task in plan.get_ready_tasks()] == ["structure"]
    plan.start_task("structure")
    plan.complete_task("structure")
    assert [task.task_id for task in plan.get_ready_tasks()] == ["security", "style"]


def test_scheduler_runs_independent_tasks_after_dependency_completion() -> None:
    plan = CodeReviewPlan(
        [
            CodeReviewTask(task_id="structure", agent_name="structure"),
            CodeReviewTask(task_id="security", agent_name="security", depends_on=["structure"]),
            CodeReviewTask(task_id="style", agent_name="style", depends_on=["structure"]),
        ]
    )
    agents = {
        "structure": RecordingAgent("structure"),
        "security": RecordingAgent("security"),
        "style": RecordingAgent("style"),
    }
    recovery = CodeReviewErrorRecovery(AppSettings(), list(agents))

    execution = asyncio.run(TaskScheduler(agents, recovery).run(plan, _build_context()))

    assert execution.ready_order == ["structure", "security", "style"]
    assert execution.completed_order == ["structure", "security", "style"]
    assert execution.failed_tasks == []
    assert execution.progress == 1.0


def test_scheduler_isolates_failed_task_from_other_branch() -> None:
    plan = CodeReviewPlan(
        [
            CodeReviewTask(task_id="structure", agent_name="structure"),
            CodeReviewTask(task_id="security", agent_name="security", depends_on=["structure"]),
            CodeReviewTask(task_id="style", agent_name="style", depends_on=["structure"]),
        ]
    )
    agents = {
        "structure": RecordingAgent("structure"),
        "security": FailingAgent(),
        "style": RecordingAgent("style"),
    }
    recovery = CodeReviewErrorRecovery(AppSettings(), list(agents))

    execution = asyncio.run(TaskScheduler(agents, recovery).run(plan, _build_context()))

    assert "security" in execution.failed_tasks
    assert "style" in execution.completed_order
    assert execution.progress == 1.0


def test_review_execution_service_uses_summary_task_set() -> None:
    settings = AppSettings(
        summary_task_order=["structure", "security", "test"],
        summary_task_dependencies={
            "structure": [],
            "security": ["structure"],
            "test": ["structure"],
        },
    )

    execution_service = ReviewExecutionService(settings)
    plan = execution_service._build_plan(summary_only=True)

    assert list(plan.tasks) == ["structure", "security", "test"]
