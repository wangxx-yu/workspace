from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CodeReviewTask:
    task_id: str
    agent_name: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"


class CodeReviewPlan:
    def __init__(self, tasks: list[CodeReviewTask]) -> None:
        self.tasks = {task.task_id: task for task in tasks}

    def get_ready_tasks(self) -> list[CodeReviewTask]:
        ready: list[CodeReviewTask] = []
        for task in self.tasks.values():
            if task.status != "pending":
                continue
            if all(self.tasks[dependency].status == "completed" for dependency in task.depends_on):
                ready.append(task)
        ready.sort(key=lambda item: item.task_id)
        return ready

    def start_task(self, task_id: str) -> None:
        self.tasks[task_id].status = "running"

    def complete_task(self, task_id: str) -> None:
        self.tasks[task_id].status = "completed"

    def fail_task(self, task_id: str) -> None:
        self.tasks[task_id].status = "failed"

    def is_complete(self) -> bool:
        return all(task.status in {"completed", "failed"} for task in self.tasks.values())

    def get_progress(self) -> float:
        if not self.tasks:
            return 1.0
        done = sum(1 for task in self.tasks.values() if task.status in {"completed", "failed"})
        return done / len(self.tasks)
