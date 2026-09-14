from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must be UTC")


@dataclass(frozen=True)
class CAIERecommendationRecord:
    proposal_id: str
    expected_value_pct: Decimal
    confidence: Decimal
    recommended_capital: Decimal
    recorded_at_utc: datetime

    def __post_init__(self) -> None:
        if not self.proposal_id.strip():
            raise ValueError("proposal_id is required")
        if not (Decimal("0") <= self.confidence <= Decimal("1")):
            raise ValueError("confidence must be in [0, 1]")
        if self.recommended_capital < 0:
            raise ValueError("recommended_capital must be non-negative")
        _require_utc(self.recorded_at_utc)


@dataclass(frozen=True)
class CAIEOutcomeRecord:
    proposal_id: str
    realized_return_pct: Decimal
    closed_at_utc: datetime

    def __post_init__(self) -> None:
        if not self.proposal_id.strip():
            raise ValueError("proposal_id is required")
        _require_utc(self.closed_at_utc)


@dataclass(frozen=True)
class CAIEMatchedOutcome:
    recommendation: CAIERecommendationRecord
    outcome: CAIEOutcomeRecord


class CAIELearningLog:
    """Append-only in-memory shadow log; it never alters live allocation."""

    def __init__(self) -> None:
        self._recommendations: dict[str, CAIERecommendationRecord] = {}
        self._outcomes: dict[str, CAIEOutcomeRecord] = {}

    def record_recommendation(self, record: CAIERecommendationRecord) -> bool:
        if record.proposal_id in self._recommendations:
            return False
        self._recommendations[record.proposal_id] = record
        return True

    def record_outcome(self, record: CAIEOutcomeRecord) -> bool:
        if record.proposal_id in self._outcomes:
            return False
        self._outcomes[record.proposal_id] = record
        return True

    def matched_outcomes(self) -> tuple[CAIEMatchedOutcome, ...]:
        matched = []
        for proposal_id in sorted(set(self._recommendations) & set(self._outcomes)):
            matched.append(
                CAIEMatchedOutcome(
                    recommendation=self._recommendations[proposal_id],
                    outcome=self._outcomes[proposal_id],
                )
            )
        return tuple(matched)

    def snapshot(self) -> dict:
        return {
            "recommendation_count": len(self._recommendations),
            "outcome_count": len(self._outcomes),
            "matched_count": len(self.matched_outcomes()),
            "mode": "SHADOW_ONLY",
            "automated_learning_enabled": False,
            "execution_allowed": False,
        }
