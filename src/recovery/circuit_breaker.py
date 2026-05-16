from __future__ import annotations

import time

from src.common.schemas import CircuitBreakerState


class CircuitBreaker:
    def __init__(self, agent_name: str, failure_threshold: int, reset_seconds: int) -> None:
        self.agent_name = agent_name
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._state = CircuitBreakerState(agent_name=agent_name)

    def before_call(self, now: float | None = None) -> bool:
        current_time = now if now is not None else time.time()
        if self._state.status == "open" and self._state.opened_at_epoch is not None:
            if current_time - self._state.opened_at_epoch >= self.reset_seconds:
                self._state.status = "half_open"
                return True
            return False
        return True

    def record_success(self) -> None:
        self._state.status = "closed"
        self._state.consecutive_failures = 0
        self._state.opened_at_epoch = None

    def record_failure(self, now: float | None = None) -> None:
        current_time = now if now is not None else time.time()
        self._state.consecutive_failures += 1
        if self._state.consecutive_failures >= self.failure_threshold:
            self._state.status = "open"
            self._state.opened_at_epoch = current_time
        elif self._state.status == "half_open":
            self._state.status = "open"
            self._state.opened_at_epoch = current_time

    def snapshot(self) -> CircuitBreakerState:
        return CircuitBreakerState.model_validate(self._state.model_dump())
