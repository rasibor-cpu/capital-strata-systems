from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from backend.options.options_income_strategy_domain import CASH_SECURED_PUT, COVERED_CALL
from backend.options.paper_position_repository import PaperIncomePosition, SAFE_FLAGS
from backend.options.position_health import PositionHealthAnalyzer, PositionHealthError, PositionHealthSnapshot
from backend.options.position_state_machine import ACTIVE, EXPIRING


class RollingCandidateError(ValueError):
    """Raised when paper roll candidates cannot be generated safely."""


@dataclass(frozen=True)
class RollingCandidate:
    position_id: str
    recommendation: str
    reason: str
    target_expiry: str
    target_strike: float
    expected_premium: float
    capital_impact: float
    yield_impact: float
    risk_impact: str
    confidence: float
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "recommendation": self.recommendation,
            "reason": self.reason,
            "target_expiry": self.target_expiry,
            "target_strike": self.target_strike,
            "expected_premium": self.expected_premium,
            "capital_impact": self.capital_impact,
            "yield_impact": self.yield_impact,
            "risk_impact": self.risk_impact,
            "confidence": self.confidence,
            **SAFE_FLAGS,
        }


class RollingCandidateGenerator:
    def __init__(self, health_analyzer: PositionHealthAnalyzer | None = None) -> None:
        self.health_analyzer = health_analyzer or PositionHealthAnalyzer()

    def generate(
        self,
        position: PaperIncomePosition,
        *,
        as_of: date | datetime | str,
        underlying_price: float,
        delta: float,
        moneyness: str,
        strategy_quality: float = 0.75,
    ) -> list[RollingCandidate]:
        if position.current_state not in {ACTIVE, EXPIRING}:
            raise RollingCandidateError("Roll candidates require ACTIVE or EXPIRING paper positions")
        health = self.health_analyzer.calculate(
            position,
            as_of=as_of,
            underlying_price=underlying_price,
            delta=delta,
            moneyness=moneyness,
        )
        if not health.roll_eligible:
            return [self._no_roll(position, health, reason="Roll thresholds not met.")]
        expiry = _as_date(position.expiry, "expiry")
        target_expiry = (expiry + timedelta(days=30)).isoformat()
        quality = _clamp(float(strategy_quality))
        premium_base = max(0.01, position.premium_remaining)
        candidates: list[RollingCandidate] = []
        if str(moneyness or "").upper() == "ITM":
            candidates.append(self._directional_roll(position, health, target_expiry, premium_base, quality, underlying_price))
        if health.days_remaining <= 7:
            candidates.append(
                RollingCandidate(
                    position_id=position.position_id,
                    recommendation="Roll Out",
                    reason="Near-expiry position with roll eligibility.",
                    target_expiry=target_expiry,
                    target_strike=position.strike,
                    expected_premium=round(premium_base * (1.15 + quality * 0.25), 6),
                    capital_impact=0.0,
                    yield_impact=round(0.01 + quality * 0.02, 6),
                    risk_impact="EXTENDS_DURATION",
                    confidence=round(0.62 + quality * 0.25, 6),
                )
            )
        candidates.append(
            RollingCandidate(
                position_id=position.position_id,
                recommendation="Roll Forward",
                reason="Maintain income exposure with refreshed premium.",
                target_expiry=target_expiry,
                target_strike=position.strike,
                expected_premium=round(premium_base * (1.05 + quality * 0.15), 6),
                capital_impact=0.0,
                yield_impact=round(0.005 + quality * 0.015, 6),
                risk_impact="SIMILAR_RISK",
                confidence=round(0.55 + quality * 0.20, 6),
            )
        )
        return sorted(candidates, key=lambda item: (-item.confidence, item.recommendation))

    def _directional_roll(
        self,
        position: PaperIncomePosition,
        health: PositionHealthSnapshot,
        target_expiry: str,
        premium_base: float,
        quality: float,
        underlying_price: float,
    ) -> RollingCandidate:
        if position.strategy_type == COVERED_CALL:
            target_strike = max(position.strike, round(float(underlying_price) * 1.02, 2))
            action = "Roll Up"
            capital_impact = 0.0
            risk = "REDUCES_CALL_AWAY_PRESSURE"
        elif position.strategy_type == CASH_SECURED_PUT:
            target_strike = min(position.strike, round(float(underlying_price) * 0.98, 2))
            action = "Roll Down"
            capital_impact = round((target_strike - position.strike) * position.quantity, 6)
            risk = "REDUCES_ASSIGNMENT_PRESSURE"
        else:
            raise RollingCandidateError(f"Unsupported strategy: {position.strategy_type}")
        return RollingCandidate(
            position_id=position.position_id,
            recommendation=action,
            reason=f"{health.assignment_exposure} assignment exposure detected.",
            target_expiry=target_expiry,
            target_strike=round(target_strike, 6),
            expected_premium=round(premium_base * (1.10 + quality * 0.20), 6),
            capital_impact=capital_impact,
            yield_impact=round(0.01 + quality * 0.015, 6),
            risk_impact=risk,
            confidence=round(0.65 + quality * 0.25, 6),
        )

    @staticmethod
    def _no_roll(position: PaperIncomePosition, health: PositionHealthSnapshot, *, reason: str) -> RollingCandidate:
        return RollingCandidate(
            position_id=position.position_id,
            recommendation="No Roll",
            reason=reason,
            target_expiry=position.expiry,
            target_strike=position.strike,
            expected_premium=0.0,
            capital_impact=0.0,
            yield_impact=0.0,
            risk_impact=f"HEALTH_SCORE_{health.health_score}",
            confidence=1.0,
        )


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip()).date()
        except (TypeError, ValueError) as exc:
            raise RollingCandidateError(f"Invalid {field}") from exc
    raise RollingCandidateError(f"Invalid {field}")


def _clamp(value: float) -> float:
    if value != value:
        raise PositionHealthError("strategy_quality must be finite")
    return max(0.0, min(1.0, value))


__all__ = ["RollingCandidate", "RollingCandidateError", "RollingCandidateGenerator"]
