from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from backend.options.paper_position_repository import SAFE_FLAGS
from backend.options.rolling_candidates import RollingCandidate


class RollDecisionError(ValueError):
    """Raised when paper roll recommendations cannot be selected safely."""


@dataclass(frozen=True)
class RollDecision:
    position_id: str
    recommendation: str
    reason: str
    expected_premium: float
    capital_impact: float
    yield_impact: float
    risk_impact: str
    confidence: float
    candidate_count: int
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "recommendation": self.recommendation,
            "reason": self.reason,
            "expected_premium": self.expected_premium,
            "capital_impact": self.capital_impact,
            "yield_impact": self.yield_impact,
            "risk_impact": self.risk_impact,
            "confidence": self.confidence,
            "candidate_count": self.candidate_count,
            **SAFE_FLAGS,
        }


class RollDecisionEngine:
    def decide(self, candidates: Sequence[RollingCandidate]) -> RollDecision:
        if not candidates:
            raise RollDecisionError("No rolling candidates supplied")
        for candidate in candidates:
            if candidate.execution_allowed is not False or candidate.advisory_only is not True:
                raise RollDecisionError("Unsafe rolling candidate flags")
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.recommendation == "No Roll",
                -float(item.confidence),
                -float(item.expected_premium),
                item.recommendation,
                item.target_expiry,
                item.target_strike,
            ),
        )
        best = ordered[0]
        return RollDecision(
            position_id=best.position_id,
            recommendation=best.recommendation,
            reason=best.reason,
            expected_premium=best.expected_premium,
            capital_impact=best.capital_impact,
            yield_impact=best.yield_impact,
            risk_impact=best.risk_impact,
            confidence=best.confidence,
            candidate_count=len(candidates),
        )


__all__ = ["RollDecision", "RollDecisionEngine", "RollDecisionError"]
