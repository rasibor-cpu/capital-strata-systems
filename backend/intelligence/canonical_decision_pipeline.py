from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.analytics.learning_pipeline_integration import LearningPipelineIntegration
from backend.intelligence.intelligence_orchestrator import IntelligenceDecision, IntelligenceOrchestrator
from backend.monitoring.alert_repository import AlertRepository
from backend.monitoring.notification_dispatcher import NotificationDispatcher, dispatch_critical_alerts
from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor


class CanonicalDecisionPipelineError(RuntimeError):
    """Fail-closed exception for canonical decision pipeline integration."""


@dataclass(frozen=True)
class CanonicalCycleResult:
    canonical_decision: dict[str, Any]
    learning_result: dict[str, Any]
    alerts: tuple[dict[str, Any], ...]
    notifications: tuple[dict[str, Any], ...]


class CanonicalDecisionPipeline:
    """Single-pass integration path that fans out one canonical decision object."""

    def __init__(
        self,
        *,
        orchestrator: IntelligenceOrchestrator,
        learning_pipeline: LearningPipelineIntegration,
        alert_repository: AlertRepository,
        notification_dispatcher: NotificationDispatcher,
        runtime_supervisor: CSSRuntimeSupervisor | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.learning_pipeline = learning_pipeline
        self.alert_repository = alert_repository
        self.notification_dispatcher = notification_dispatcher
        self.runtime_supervisor = runtime_supervisor

    def evaluate_cycle(
        self,
        *,
        trade_candidate: Mapping[str, Any],
        completed_trade: Mapping[str, Any] | None = None,
        previous_canonical_decision: Mapping[str, Any] | None = None,
        rejection_streak: int = 0,
    ) -> CanonicalCycleResult:
        if not isinstance(trade_candidate, Mapping):
            raise CanonicalDecisionPipelineError("trade_candidate must be a mapping")

        decision: IntelligenceDecision = self.orchestrator.decide(trade_candidate)
        canonical = decision.to_dict()

        if self.runtime_supervisor is not None:
            self.runtime_supervisor.record_canonical_decision(canonical)

        learning_result: dict[str, Any] = {}
        if completed_trade is not None:
            if not isinstance(completed_trade, Mapping):
                raise CanonicalDecisionPipelineError("completed_trade must be a mapping when provided")
            learning_result = self.learning_pipeline.write_completed_trade(
                completed_trade,
                canonical_decision=canonical,
            )

        alerts = self.alert_repository.persist_decision_alerts(
            canonical,
            previous_decision=dict(previous_canonical_decision or {}),
            rejection_streak=int(rejection_streak),
        )
        notifications = dispatch_critical_alerts(
            self.alert_repository,
            self.notification_dispatcher,
        )

        return CanonicalCycleResult(
            canonical_decision=canonical,
            learning_result=learning_result,
            alerts=tuple(alerts),
            notifications=tuple(notifications),
        )
