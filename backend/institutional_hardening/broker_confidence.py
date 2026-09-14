from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BrokerConfidenceInput:
    freshness: Decimal
    account_match: Decimal
    position_match: Decimal
    heartbeat: Decimal

    def __post_init__(self) -> None:
        for value in (self.freshness, self.account_match, self.position_match, self.heartbeat):
            if value < 0 or value > 1:
                raise ValueError("confidence components must be in [0, 1]")


@dataclass(frozen=True)
class BrokerConfidenceResult:
    score: Decimal
    status: str
    safe_degradation_required: bool


def score_broker_confidence(
    data: BrokerConfidenceInput,
    *,
    degradation_threshold: Decimal = Decimal("0.80"),
) -> BrokerConfidenceResult:
    score = (
        data.freshness * Decimal("0.30")
        + data.account_match * Decimal("0.25")
        + data.position_match * Decimal("0.30")
        + data.heartbeat * Decimal("0.15")
    )
    score = score.quantize(Decimal("0.0001"))
    degraded = score < degradation_threshold
    return BrokerConfidenceResult(
        score=score,
        status="DEGRADED" if degraded else "CONFIDENT",
        safe_degradation_required=degraded,
    )
