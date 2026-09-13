from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Iterable, Sequence

from .models import ChallengeDefinition, ChallengeProgress, SimulationScore


class LessonStatus(str, Enum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class Lesson:
    lesson_id: str
    title: str
    sequence: int
    prerequisite_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.lesson_id.strip():
            raise ValueError("lesson_id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if self.sequence < 1:
            raise ValueError("sequence must be >= 1")


@dataclass(frozen=True)
class LessonProgress:
    lesson_id: str
    status: LessonStatus
    completed_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if self.completed_at_utc is not None:
            if self.completed_at_utc.tzinfo is None or self.completed_at_utc.utcoffset() != timedelta(0):
                raise ValueError("completed_at_utc must be timezone-aware UTC")


class DecisionAction(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


class DecisionOutcome(str, Enum):
    GOOD = "GOOD"
    BAD = "BAD"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RecommendationDecision:
    decision_id: str
    recommendation_id: str
    action: DecisionAction
    recorded_at_utc: datetime
    outcome: DecisionOutcome = DecisionOutcome.UNKNOWN
    note: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.recommendation_id.strip():
            raise ValueError("decision_id and recommendation_id are required")
        if self.recorded_at_utc.tzinfo is None or self.recorded_at_utc.utcoffset() != timedelta(0):
            raise ValueError("recorded_at_utc must be timezone-aware UTC")


@dataclass(frozen=True)
class Achievement:
    achievement_id: str
    awarded_at_utc: datetime
    source: str

    def __post_init__(self) -> None:
        if not self.achievement_id.strip():
            raise ValueError("achievement_id is required")
        if self.awarded_at_utc.tzinfo is None or self.awarded_at_utc.utcoffset() != timedelta(0):
            raise ValueError("awarded_at_utc must be timezone-aware UTC")
        if not self.source.strip():
            raise ValueError("source is required")


class AcademyProgression:
    @staticmethod
    def lesson_states(
        lessons: Sequence[Lesson],
        completed_ids: set[str],
    ) -> tuple[LessonProgress, ...]:
        known_ids = {lesson.lesson_id for lesson in lessons}
        unknown = completed_ids - known_ids
        if unknown:
            raise ValueError(f"unknown completed lessons: {sorted(unknown)}")

        states: list[LessonProgress] = []
        for lesson in sorted(lessons, key=lambda item: item.sequence):
            if lesson.lesson_id in completed_ids:
                states.append(LessonProgress(lesson.lesson_id, LessonStatus.COMPLETED))
            elif all(req in completed_ids for req in lesson.prerequisite_ids):
                states.append(LessonProgress(lesson.lesson_id, LessonStatus.AVAILABLE))
            else:
                states.append(LessonProgress(lesson.lesson_id, LessonStatus.LOCKED))
        return tuple(states)

    @staticmethod
    def decision_quality(decisions: Iterable[RecommendationDecision]) -> tuple[int, int, int]:
        accepted_good = 0
        rejected_bad = 0
        total = 0
        for decision in decisions:
            total += 1
            if decision.action == DecisionAction.ACCEPT and decision.outcome == DecisionOutcome.GOOD:
                accepted_good += 1
            if decision.action == DecisionAction.REJECT and decision.outcome == DecisionOutcome.BAD:
                rejected_bad += 1
        return accepted_good, rejected_bad, total

    @staticmethod
    def achievements_from_challenges(
        progress: Iterable[ChallengeProgress],
        awarded_at_utc: datetime,
    ) -> tuple[Achievement, ...]:
        if awarded_at_utc.tzinfo is None or awarded_at_utc.utcoffset() != timedelta(0):
            raise ValueError("awarded_at_utc must be timezone-aware UTC")
        return tuple(
            Achievement(
                achievement_id=item.challenge_id,
                awarded_at_utc=awarded_at_utc,
                source="CHALLENGE",
            )
            for item in sorted(progress, key=lambda x: x.challenge_id)
            if item.complete
        )


def default_challenge_catalog() -> tuple[ChallengeDefinition, ...]:
    from .models import ChallengeType

    return (
        ChallengeDefinition(
            "preserve-capital-20",
            ChallengeType.CAPITAL_PRESERVATION,
            Decimal("1"),
            minimum_observations=20,
        ),
        ChallengeDefinition(
            "beat-benchmark-30",
            ChallengeType.BENCHMARK_OUTPERFORMANCE,
            Decimal("0"),
            minimum_observations=30,
        ),
        ChallengeDefinition(
            "drawdown-under-5pct",
            ChallengeType.DRAWDOWN_CONTROL,
            Decimal("0.05"),
            minimum_observations=20,
        ),
        ChallengeDefinition(
            "decision-quality-80pct",
            ChallengeType.DECISION_DISCIPLINE,
            Decimal("0.80"),
            minimum_observations=10,
        ),
    )
