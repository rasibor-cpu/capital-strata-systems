from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from backend.options.options_income_strategy_domain import CASH_SECURED_PUT, COVERED_CALL
from backend.options.paper_position_repository import PaperIncomePosition, SAFE_FLAGS
from backend.options.position_state_machine import ACTIVE, ASSIGNED, CLOSED_EARLY, COMPLETED, EXERCISED, EXPIRING, EXPIRED_WORTHLESS, VALID_STATES


class PositionHealthError(ValueError):
    """Raised when paper position health cannot be calculated safely."""


@dataclass(frozen=True)
class PositionHealthSnapshot:
    position_id: str
    current_state: str
    days_remaining: int
    premium_retained: float
    premium_capture_pct: float
    premium_decay: float
    collateral_utilization: float
    yield_remaining: float
    assignment_exposure: str
    early_close_eligible: bool
    roll_eligible: bool
    health_score: float
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "current_state": self.current_state,
            "days_remaining": self.days_remaining,
            "premium_retained": self.premium_retained,
            "premium_capture_pct": self.premium_capture_pct,
            "premium_decay": self.premium_decay,
            "collateral_utilization": self.collateral_utilization,
            "yield_remaining": self.yield_remaining,
            "assignment_exposure": self.assignment_exposure,
            "early_close_eligible": self.early_close_eligible,
            "roll_eligible": self.roll_eligible,
            "health_score": self.health_score,
            **SAFE_FLAGS,
        }


class PositionHealthAnalyzer:
    def calculate(
        self,
        position: PaperIncomePosition,
        *,
        as_of: date | datetime | str,
        underlying_price: float | None = None,
        delta: float | None = None,
        moneyness: str | None = None,
    ) -> PositionHealthSnapshot:
        _validate_position(position)
        today = _as_date(as_of, "as_of")
        expiry = _as_date(position.expiry, "expiry")
        days_remaining = max(0, (expiry - today).days)
        total_days = max(1, (_as_date(position.expiry, "expiry") - _as_date(position.entry_date, "entry_date")).days)
        elapsed_days = max(0, total_days - days_remaining)

        premium_received = _non_negative(position.premium_received, "premium_received")
        premium_remaining = _non_negative(position.premium_remaining, "premium_remaining")
        collateral = _non_negative(position.collateral_reserved, "collateral_reserved")
        premium_retained = max(0.0, premium_received - premium_remaining)
        premium_capture_pct = premium_retained / premium_received if premium_received > 0.0 else 0.0
        premium_decay = min(1.0, elapsed_days / total_days)
        collateral_utilization = 1.0 if collateral > 0.0 and position.current_state in {ACTIVE, EXPIRING} else 0.0
        yield_remaining = premium_remaining / collateral if collateral > 0.0 else 0.0

        exposure = _assignment_exposure(position, underlying_price=underlying_price, moneyness=moneyness)
        early_close = position.current_state in {ACTIVE, EXPIRING} and premium_capture_pct >= 0.5
        roll = position.current_state in {ACTIVE, EXPIRING} and (
            days_remaining <= 7 or exposure in {"ITM", "NEAR_MONEY"} or abs(float(delta or 0.0)) >= 0.45
        )
        score = _health_score(
            days_remaining=days_remaining,
            premium_capture_pct=premium_capture_pct,
            assignment_exposure=exposure,
            roll_eligible=roll,
            state=position.current_state,
        )
        return PositionHealthSnapshot(
            position_id=position.position_id,
            current_state=position.current_state,
            days_remaining=days_remaining,
            premium_retained=round(premium_retained, 6),
            premium_capture_pct=round(premium_capture_pct, 6),
            premium_decay=round(premium_decay, 6),
            collateral_utilization=round(collateral_utilization, 6),
            yield_remaining=round(yield_remaining, 8),
            assignment_exposure=exposure,
            early_close_eligible=early_close,
            roll_eligible=roll,
            health_score=score,
        )


def _validate_position(position: PaperIncomePosition) -> None:
    if position is None:
        raise PositionHealthError("Missing paper position")
    if position.current_state not in VALID_STATES:
        raise PositionHealthError(f"Invalid paper position state: {position.current_state}")
    if position.strategy_type not in {COVERED_CALL, CASH_SECURED_PUT}:
        raise PositionHealthError(f"Unsupported strategy: {position.strategy_type}")
    if {**SAFE_FLAGS, **dict(position.advisory_flags or {})} != SAFE_FLAGS:
        raise PositionHealthError("Unsafe advisory flags on paper position")
    _non_negative(position.premium_received, "premium_received")
    _non_negative(position.premium_remaining, "premium_remaining")
    _non_negative(position.collateral_reserved, "collateral_reserved")


def _assignment_exposure(position: PaperIncomePosition, *, underlying_price: float | None, moneyness: str | None) -> str:
    if position.current_state in {COMPLETED, EXPIRED_WORTHLESS, CLOSED_EARLY}:
        return "NONE"
    if position.current_state in {ASSIGNED, EXERCISED}:
        return position.current_state
    label = str(moneyness or "").strip().upper()
    if label in {"ITM", "OTM", "ATM", "NEAR_MONEY"}:
        return "NEAR_MONEY" if label == "ATM" else label
    if underlying_price is None:
        return "UNKNOWN"
    price = _positive(underlying_price, "underlying_price")
    distance = abs(price - position.strike) / position.strike
    if distance <= 0.01:
        return "NEAR_MONEY"
    if position.strategy_type == COVERED_CALL:
        return "ITM" if price > position.strike else "OTM"
    return "ITM" if price < position.strike else "OTM"


def _health_score(*, days_remaining: int, premium_capture_pct: float, assignment_exposure: str, roll_eligible: bool, state: str) -> float:
    if state == COMPLETED:
        return 100.0
    score = 70.0 + premium_capture_pct * 20.0
    if assignment_exposure == "ITM":
        score -= 25.0
    elif assignment_exposure == "NEAR_MONEY":
        score -= 10.0
    if days_remaining <= 3:
        score -= 10.0
    if roll_eligible:
        score -= 5.0
    return round(max(0.0, min(100.0, score)), 6)


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip()).date()
        except (TypeError, ValueError) as exc:
            raise PositionHealthError(f"Invalid {field}") from exc
    raise PositionHealthError(f"Invalid {field}")


def _non_negative(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PositionHealthError(f"{field} must be numeric") from exc
    if number < 0.0:
        raise PositionHealthError(f"{field} cannot be negative")
    return number


def _positive(value: Any, field: str) -> float:
    number = _non_negative(value, field)
    if number <= 0.0:
        raise PositionHealthError(f"{field} must be positive")
    return number


__all__ = ["PositionHealthAnalyzer", "PositionHealthError", "PositionHealthSnapshot"]
