from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class ReadinessLevel(str, Enum):
    FOUNDATION = "FOUNDATION"
    PRACTICE = "PRACTICE"
    BROKER_READONLY_READY = "BROKER_READONLY_READY"
    ADVISORY_READY = "ADVISORY_READY"
    CONTROLLED_LIVE_REVIEW = "CONTROLLED_LIVE_REVIEW"


@dataclass(frozen=True)
class ReadinessAssessment:
    level: ReadinessLevel
    completed_lessons: int
    completed_scenarios: int
    decision_quality_pct: Decimal
    max_drawdown_pct: Decimal
    live_execution_authorized: bool
    reasons: tuple[str, ...]


class ReadinessEngine:
    """Educational readiness only; never grants live execution authority."""

    @staticmethod
    def assess(
        *,
        completed_lessons: int,
        completed_scenarios: int,
        decision_quality_pct: Decimal,
        max_drawdown_pct: Decimal,
    ) -> ReadinessAssessment:
        if completed_lessons < 0 or completed_scenarios < 0:
            raise ValueError("completion counts must be non-negative")
        if decision_quality_pct < Decimal("0") or decision_quality_pct > Decimal("1"):
            raise ValueError("decision_quality_pct must be between 0 and 1")
        if max_drawdown_pct < Decimal("0"):
            raise ValueError("max_drawdown_pct must be non-negative")

        reasons: list[str] = []
        level = ReadinessLevel.FOUNDATION

        if completed_lessons >= 2:
            level = ReadinessLevel.PRACTICE
        else:
            reasons.append("Complete at least two foundation lessons.")

        if (
            completed_lessons >= 4
            and completed_scenarios >= 2
            and decision_quality_pct >= Decimal("0.70")
        ):
            level = ReadinessLevel.BROKER_READONLY_READY
        else:
            reasons.append(
                "Broker read-only readiness requires 4 lessons, 2 scenarios, and 70% decision quality."
            )

        if (
            completed_lessons >= 6
            and completed_scenarios >= 4
            and decision_quality_pct >= Decimal("0.80")
            and max_drawdown_pct <= Decimal("0.10")
        ):
            level = ReadinessLevel.ADVISORY_READY
        else:
            reasons.append(
                "Advisory readiness requires 6 lessons, 4 scenarios, 80% decision quality, and <=10% drawdown."
            )

        if (
            completed_lessons >= 8
            and completed_scenarios >= 6
            and decision_quality_pct >= Decimal("0.90")
            and max_drawdown_pct <= Decimal("0.05")
        ):
            level = ReadinessLevel.CONTROLLED_LIVE_REVIEW
            reasons.append(
                "Training threshold met; separate operational, broker, compliance, and explicit human approval remain required."
            )

        return ReadinessAssessment(
            level=level,
            completed_lessons=completed_lessons,
            completed_scenarios=completed_scenarios,
            decision_quality_pct=decision_quality_pct,
            max_drawdown_pct=max_drawdown_pct,
            live_execution_authorized=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
