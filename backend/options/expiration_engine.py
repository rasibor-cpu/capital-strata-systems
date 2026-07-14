from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from backend.options.assignment_simulator import AssignmentSimulator
from backend.options.paper_position_repository import PaperIncomePosition


class ExpirationEngineError(ValueError):
    """Raised when paper expiration processing cannot be evaluated safely."""


@dataclass(frozen=True)
class ExpirationResult:
    expired: bool
    outcome: str
    assignment_status: str
    intrinsic_value: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "expired": self.expired,
            "outcome": self.outcome,
            "assignment_status": self.assignment_status,
            "intrinsic_value": self.intrinsic_value,
            "reason": self.reason,
        }


class ExpirationEngine:
    """Paper-only expiration processor for short-premium income positions."""

    def __init__(self, simulator: AssignmentSimulator | None = None) -> None:
        self.simulator = simulator or AssignmentSimulator()

    def process(
        self,
        position: PaperIncomePosition,
        *,
        underlying_price: float,
        as_of: date | datetime | str,
        close_early: bool = False,
        force_exercised: bool = False,
    ) -> ExpirationResult:
        expiry = _as_date(position.expiry, "expiry")
        evaluation_date = _as_date(as_of, "as_of")
        if not close_early and evaluation_date < expiry:
            raise ExpirationEngineError("Expiration date has not been reached")

        outcome = self.simulator.evaluate(
            strategy_type=position.strategy_type,
            strike=position.strike,
            underlying_price=underlying_price,
            close_early=close_early,
            force_exercised=force_exercised,
        )
        return ExpirationResult(
            expired=not close_early,
            outcome=outcome.outcome,
            assignment_status=outcome.assignment_status,
            intrinsic_value=outcome.intrinsic_value,
            reason=outcome.reason,
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
            raise ExpirationEngineError(f"Malformed {field}") from exc
    raise ExpirationEngineError(f"Malformed {field}")


__all__ = ["ExpirationEngine", "ExpirationEngineError", "ExpirationResult"]
