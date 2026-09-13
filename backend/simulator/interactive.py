from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from .academy import DecisionAction, DecisionOutcome, RecommendationDecision
from .profile import LearnerProfile
from .replay import RecommendationCheckpoint, RecommendationReplayEngine
from .scenarios import Scenario


class InteractiveStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_DECISION = "AWAITING_DECISION"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class InteractiveScenarioSession:
    learner_id: str
    scenario_id: str
    step_index: int
    status: InteractiveStatus
    started_at_utc: datetime
    updated_at_utc: datetime
    completed_at_utc: datetime | None = None
    decision_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("started_at_utc", self.started_at_utc),
            ("updated_at_utc", self.updated_at_utc),
        ):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError(f"{name} must be timezone-aware UTC")
        if self.completed_at_utc is not None:
            if self.completed_at_utc.tzinfo is None or self.completed_at_utc.utcoffset() != timedelta(0):
                raise ValueError("completed_at_utc must be timezone-aware UTC")
        if self.step_index < 0:
            raise ValueError("step_index must be non-negative")

    def advance(self, scenario: Scenario, at_utc: datetime) -> "InteractiveScenarioSession":
        if at_utc.tzinfo is None or at_utc.utcoffset() != timedelta(0):
            raise ValueError("at_utc must be timezone-aware UTC")
        next_index = min(self.step_index + 1, len(scenario.price_path) - 1)
        complete = next_index == len(scenario.price_path) - 1
        return replace(
            self,
            step_index=next_index,
            status=InteractiveStatus.COMPLETE if complete else InteractiveStatus.IN_PROGRESS,
            updated_at_utc=at_utc,
            completed_at_utc=at_utc if complete else None,
        )

    def attach_decision(self, decision: RecommendationDecision) -> "InteractiveScenarioSession":
        ids = tuple(sorted(set(self.decision_ids) | {decision.decision_id}))
        return replace(self, decision_ids=ids, updated_at_utc=decision.recorded_at_utc)


@dataclass(frozen=True)
class DecisionPrompt:
    checkpoint_id: str
    recommendation_id: str
    title: str
    prompt: str
    choices: tuple[str, ...] = ("ACCEPT", "REJECT", "MODIFY")


class InteractiveScenarioEngine:
    @staticmethod
    def start(learner_id: str, scenario: Scenario, at_utc: datetime) -> InteractiveScenarioSession:
        if at_utc.tzinfo is None or at_utc.utcoffset() != timedelta(0):
            raise ValueError("at_utc must be timezone-aware UTC")
        return InteractiveScenarioSession(
            learner_id=learner_id,
            scenario_id=scenario.scenario_id,
            step_index=0,
            status=InteractiveStatus.IN_PROGRESS,
            started_at_utc=at_utc,
            updated_at_utc=at_utc,
        )

    @staticmethod
    def prompt_for_checkpoint(checkpoint: RecommendationCheckpoint) -> DecisionPrompt:
        return DecisionPrompt(
            checkpoint_id=checkpoint.checkpoint_id,
            recommendation_id=checkpoint.recommendation_id,
            title=checkpoint.title,
            prompt=f"CSS scenario decision: {checkpoint.title}. What would you do?",
        )

    @staticmethod
    def record_prompt_decision(
        profile: LearnerProfile,
        session: InteractiveScenarioSession,
        *,
        checkpoint: RecommendationCheckpoint,
        decision_id: str,
        action: DecisionAction,
        at_utc: datetime,
        note: str = "",
    ) -> tuple[LearnerProfile, InteractiveScenarioSession]:
        decision = RecommendationDecision(
            decision_id=decision_id,
            recommendation_id=checkpoint.recommendation_id,
            action=action,
            recorded_at_utc=at_utc,
            outcome=DecisionOutcome.UNKNOWN,
            note=note,
        )
        return profile.record_decision(decision), session.attach_decision(decision)
