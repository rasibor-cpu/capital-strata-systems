from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from backend.options.paper_position_repository import PaperIncomePosition, SAFE_FLAGS
from backend.options.position_health import PositionHealthError


@dataclass(frozen=True)
class IncomePositionMetrics:
    position_id: str
    lifetime_premium: float
    annualized_yield: float
    yield_per_collateral: float
    position_duration: int
    rolling_history: list[dict[str, Any]]
    assignment_history: list[dict[str, Any]]
    premium_capture_pct: float
    capital_efficiency: float
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "lifetime_premium": self.lifetime_premium,
            "annualized_yield": self.annualized_yield,
            "yield_per_collateral": self.yield_per_collateral,
            "position_duration": self.position_duration,
            "rolling_history": self.rolling_history,
            "assignment_history": self.assignment_history,
            "premium_capture_pct": self.premium_capture_pct,
            "capital_efficiency": self.capital_efficiency,
            **SAFE_FLAGS,
        }


class IncomePositionMetricsCalculator:
    def calculate(self, position: PaperIncomePosition, *, as_of: date | datetime | str) -> IncomePositionMetrics:
        if position is None:
            raise PositionHealthError("Missing paper position")
        premium = _non_negative(position.premium_received, "premium_received")
        realized = _non_negative(position.premium_realized, "premium_realized")
        collateral = _non_negative(position.collateral_reserved, "collateral_reserved")
        start = _as_date(position.entry_date, "entry_date")
        end = _as_date(as_of, "as_of")
        if end < start:
            raise PositionHealthError("as_of cannot precede entry_date")
        duration = max(0, (end - start).days)
        capture = realized / premium if premium > 0.0 else 0.0
        yield_per_collateral = realized / collateral if collateral > 0.0 else 0.0
        annualized = yield_per_collateral * (365.0 / max(1, duration)) if duration > 0 else 0.0
        rolling_history = [
            dict(event)
            for event in position.lifecycle_events
            if str(event.get("event_type", "")).lower().startswith("roll")
        ]
        assignment_history = [
            dict(event)
            for event in position.lifecycle_events
            if str(event.get("event_type", "")) in {"Assigned", "Exercised", "Expired Worthless", "Closed Early"}
        ]
        return IncomePositionMetrics(
            position_id=position.position_id,
            lifetime_premium=round(premium, 6),
            annualized_yield=round(annualized, 8),
            yield_per_collateral=round(yield_per_collateral, 8),
            position_duration=duration,
            rolling_history=rolling_history,
            assignment_history=assignment_history,
            premium_capture_pct=round(capture, 6),
            capital_efficiency=round((premium / collateral) if collateral > 0.0 else 0.0, 8),
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


__all__ = ["IncomePositionMetrics", "IncomePositionMetricsCalculator"]
