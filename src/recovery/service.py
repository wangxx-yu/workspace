from __future__ import annotations

from src.common.schemas import RecoveryEvent, RecoverySummary
from src.common.settings import AppSettings
from src.recovery.circuit_breaker import CircuitBreaker


class CodeReviewErrorRecovery:
    def __init__(self, settings: AppSettings, agent_names: list[str]) -> None:
        self.settings = settings
        self.events: list[RecoveryEvent] = []
        self.circuit_breakers = {
            agent_name: CircuitBreaker(
                agent_name=agent_name,
                failure_threshold=settings.circuit_breaker_failure_threshold,
                reset_seconds=settings.circuit_breaker_reset_seconds,
            )
            for agent_name in agent_names
        }

    def effective_mode(self) -> str:
        if self.settings.run_mode == "apply_with_git" and self.settings.allow_apply_with_git is False:
            self.events.append(
                RecoveryEvent(
                    scope="run_mode",
                    target="apply_with_git",
                    action="downgrade_to_propose_patch",
                    reason="apply_with_git_disabled",
                )
            )
            return "propose_patch"
        return self.settings.run_mode

    def can_execute(self, agent_name: str) -> bool:
        breaker = self.circuit_breakers[agent_name]
        allowed = breaker.before_call()
        if not allowed:
            self.events.append(
                RecoveryEvent(
                    scope="task",
                    target=agent_name,
                    action="fallback_skip_with_degraded_mode",
                    reason="circuit_breaker_open",
                )
            )
        return allowed

    def record_success(self, agent_name: str) -> None:
        self.circuit_breakers[agent_name].record_success()

    def record_failure(self, agent_name: str, reason: str) -> None:
        self.circuit_breakers[agent_name].record_failure()
        self.events.append(
            RecoveryEvent(
                scope="task",
                target=agent_name,
                action="record_failure",
                reason=reason,
            )
        )

    def build_summary(self) -> RecoverySummary:
        return RecoverySummary(
            mode_requested=self.settings.run_mode,
            mode_effective=self.effective_mode(),
            circuit_breakers=[breaker.snapshot() for breaker in self.circuit_breakers.values()],
            events=list(self.events),
        )
