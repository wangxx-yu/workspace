from __future__ import annotations

import asyncio
import time

from src.agents.base import BaseReviewAgent
from src.common.schemas import ReviewContext, ReviewExecution, TaskResult
from src.control.plan import CodeReviewPlan, CodeReviewTask
from src.recovery.service import CodeReviewErrorRecovery


class TaskScheduler:
    def __init__(self, agents: dict[str, BaseReviewAgent], recovery: CodeReviewErrorRecovery) -> None:
        self.agents = agents
        self.recovery = recovery

    async def run(self, plan: CodeReviewPlan, context: ReviewContext) -> ReviewExecution:
        ready_order: list[str] = []
        completed_order: list[str] = []
        failed_tasks: list[str] = []
        task_results: list[TaskResult] = []

        while not plan.is_complete():
            ready_tasks = plan.get_ready_tasks()
            if not ready_tasks:
                break

            ready_order.extend(task.task_id for task in ready_tasks)
            for task in ready_tasks:
                plan.start_task(task.task_id)

            batch_results = await asyncio.gather(
                *(self._run_single_task(task, context) for task in ready_tasks),
                return_exceptions=False,
            )

            for result in batch_results:
                task_results.append(result)
                if result.status == "completed":
                    plan.complete_task(result.task_id)
                    completed_order.append(result.task_id)
                else:
                    plan.fail_task(result.task_id)
                    failed_tasks.append(result.task_id)

        return ReviewExecution(
            ready_order=ready_order,
            completed_order=completed_order,
            failed_tasks=failed_tasks,
            task_results=task_results,
            progress=plan.get_progress(),
        )

    async def _run_single_task(self, task: CodeReviewTask, context: ReviewContext) -> TaskResult:
        started_at = time.perf_counter()
        if not self.recovery.can_execute(task.agent_name):
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            return TaskResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                status="completed",
                depends_on=task.depends_on,
                evidence=[],
                duration_ms=duration_ms,
                recovery_action="fallback_skip_with_degraded_mode",
                degraded=True,
            )
        try:
            agent = self.agents[task.agent_name]
            report = await asyncio.to_thread(agent.run, context)
            self.recovery.record_success(task.agent_name)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            return TaskResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                status="completed",
                depends_on=task.depends_on,
                issues=report.issues,
                evidence=report.evidence,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            self.recovery.record_failure(task.agent_name, str(exc))
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            return TaskResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                status="failed",
                depends_on=task.depends_on,
                evidence=[],
                error=str(exc),
                duration_ms=duration_ms,
                recovery_action="record_failure",
            )
