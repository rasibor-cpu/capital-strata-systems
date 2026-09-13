from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .academy import DecisionAction, DecisionOutcome, RecommendationDecision


class CheckpointState(str, Enum):
    PENDING = "PENDING"
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class RecommendationCheckpoint:
    checkpoint_id: str
    recommendation_id: str
    title: str
    expected_action: DecisionAction
    expected_outcome: DecisionOutcome
    score_weight: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if not self.checkpoint_id.strip() or not self.recommendation_id.strip():
            raise ValueError("checkpoint_id and recommendation_id are required")
        if not self.title.strip():
            raise ValueError("title is required")
        if self.score_weight <= Decimal("0"):
            raise ValueError("score_weight must be positive")


@dataclass(frozen=True)
class CheckpointResult:
    checkpoint_id: str
    state: CheckpointState
    earned_weight: Decimal
    possible_weight: Decimal
    explanation: str


@dataclass(frozen=True)
class ReplayScore:
    earned_weight: Decimal
    possible_weight: Decimal
    score_pct: Decimal
    correct: int
    partial: int
    incorrect: int
    pending: int


class RecommendationReplayEngine:
    """Scores historical/simulated recommendation decisions only.

    This engine does not create, modify, submit, or cancel broker orders.
    """

    @staticmethod
    def evaluate(
        checkpoints: Iterable[RecommendationCheckpoint],
        decisions: Iterable[RecommendationDecision],
    ) -> tuple[tuple[CheckpointResult, ...], ReplayScore]:
        by_recommendation = {
            decision.recommendation_id: decision for decision in decisions
        }
        results: list[CheckpointResult] = []
        earned = Decimal("0")
        possible = Decimal("0")
        counts = {
            CheckpointState.CORRECT: 0,
            CheckpointState.PARTIAL: 0,
            CheckpointState.INCORRECT: 0,
            CheckpointState.PENDING: 0,
        }

        for checkpoint in checkpoints:
            possible += checkpoint.score_weight
            decision = by_recommendation.get(checkpoint.recommendation_id)
            if decision is None:
                state = CheckpointState.PENDING
                earned_weight = Decimal("0")
                explanation = "No learner decision recorded."
            elif (
                decision.action == checkpoint.expected_action
                and decision.outcome == checkpoint.expected_outcome
            ):
                state = CheckpointState.CORRECT
                earned_weight = checkpoint.score_weight
                explanation = "Action and outcome match the scenario checkpoint."
            elif decision.action == checkpoint.expected_action:
                state = CheckpointState.PARTIAL
                earned_weight = checkpoint.score_weight / Decimal("2")
                explanation = "Action matches; outcome evidence does not fully match."
            else:
                state = CheckpointState.INCORRECT
                earned_weight = Decimal("0")
                explanation = "Action differs from the scenario checkpoint."

            earned += earned_weight
            counts[state] += 1
            results.append(
                CheckpointResult(
                    checkpoint_id=checkpoint.checkpoint_id,
                    state=state,
                    earned_weight=earned_weight,
                    possible_weight=checkpoint.score_weight,
                    explanation=explanation,
                )
            )

        score_pct = earned / possible if possible else Decimal("0")
        return tuple(results), ReplayScore(
            earned_weight=earned,
            possible_weight=possible,
            score_pct=score_pct,
            correct=counts[CheckpointState.CORRECT],
            partial=counts[CheckpointState.PARTIAL],
            incorrect=counts[CheckpointState.INCORRECT],
            pending=counts[CheckpointState.PENDING],
        )
