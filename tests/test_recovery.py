from __future__ import annotations

import asyncio

from src.agents.base import BaseReviewAgent
from src.common.schemas import AgentReport, ReviewContext
from src.common.settings import AppSettings
from src.context.manager import CodeReviewContextManager
from src.control.plan import CodeReviewPlan, CodeReviewTask
from src.control.scheduler import TaskScheduler
from src.input.dependency_extractor import DependencyExtractor
from src.input.parser import CodeParser
from src.input.repo_loader import RepoLoader
from src.input.scanner import RepositoryScanner
from src.recovery.service import CodeReviewErrorRecovery


class AlwaysFailAgent(BaseReviewAgent):
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def run(self, context: ReviewContext) -> AgentReport:
        raise RuntimeError("forced failure")


class OkAgent(BaseReviewAgent):
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def run(self, context: ReviewContext) -> AgentReport:
        return AgentReport(agent_name=self.agent_name)


def _build_context() -> ReviewContext:
    settings = AppSettings(history_file_path=".history-recovery.json")
    loaded_repo = RepoLoader(settings).load("tests/fixtures/python_sample_repo")
    repo_path = loaded_repo.path
    scanned_files, _ = RepositoryScanner(settings).scan(repo_path)
    parsed_files = [CodeParser().parse(item) for item in scanned_files]
    graph = DependencyExtractor().build_graph(parsed_files)
    return CodeReviewContextManager(settings, repo_path).build(parsed_files, graph)


def test_circuit_breaker_opens_after_threshold() -> None:
    settings = AppSettings(circuit_breaker_failure_threshold=2)
    recovery = CodeReviewErrorRecovery(settings, ["security"])

    recovery.record_failure("security", "one")
    recovery.record_failure("security", "two")

    summary = recovery.build_summary()
    state = summary.circuit_breakers[0]
    assert state.status == "open"
    assert state.consecutive_failures == 2


def test_scheduler_degrades_when_circuit_breaker_is_open() -> None:
    settings = AppSettings(circuit_breaker_failure_threshold=1)
    recovery = CodeReviewErrorRecovery(settings, ["structure"])
    recovery.record_failure("structure", "forced failure")

    plan = CodeReviewPlan([CodeReviewTask(task_id="structure", agent_name="structure")])
    scheduler = TaskScheduler({"structure": OkAgent("structure")}, recovery)
    execution = asyncio.run(scheduler.run(plan, _build_context()))

    assert execution.completed_order == ["structure"]
    assert execution.task_results[0].degraded is True
    assert execution.task_results[0].recovery_action == "fallback_skip_with_degraded_mode"


def test_run_mode_downgrades_apply_with_git_when_disabled() -> None:
    settings = AppSettings(run_mode="apply_with_git", allow_apply_with_git=False)
    recovery = CodeReviewErrorRecovery(settings, ["structure"])

    summary = recovery.build_summary()

    assert summary.mode_requested == "apply_with_git"
    assert summary.mode_effective == "propose_patch"
    assert summary.events[0].action == "downgrade_to_propose_patch"
