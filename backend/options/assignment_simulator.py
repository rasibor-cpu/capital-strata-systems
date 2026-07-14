from __future__ import annotations

from dataclasses import dataclass

from backend.options.options_income_strategy_domain import CASH_SECURED_PUT, COVERED_CALL
from backend.options.position_state_machine import ASSIGNED, CLOSED_EARLY, EXERCISED, EXPIRED_WORTHLESS


class AssignmentSimulationError(ValueError):
    """Raised when paper assignment simulation cannot be evaluated safely."""


@dataclass(frozen=True)
class AssignmentOutcome:
    outcome: str
    assignment_status: str
    intrinsic_value: float
    reason: str

    def to_dict(self) -> dict[str, str | float]:
        return {
            "outcome": self.outcome,
            "assignment_status": self.assignment_status,
            "intrinsic_value": self.intrinsic_value,
            "reason": self.reason,
        }


class AssignmentSimulator:
    def evaluate(
        self,
        *,
        strategy_type: str,
        strike: float,
        underlying_price: float,
        close_early: bool = False,
        force_exercised: bool = False,
    ) -> AssignmentOutcome:
        strategy = str(strategy_type or "").strip().upper()
        strike_value = _positive(strike, "strike")
        price = _positive(underlying_price, "underlying_price")
        if close_early:
            return AssignmentOutcome(CLOSED_EARLY, "CLOSED_EARLY", 0.0, "Position closed before expiration.")
        if force_exercised:
            intrinsic = _intrinsic(strategy, strike_value, price)
            return AssignmentOutcome(EXERCISED, "EXERCISED", intrinsic, "Paper exercise outcome forced by caller.")
        intrinsic = _intrinsic(strategy, strike_value, price)
        if intrinsic <= 0.0:
            return AssignmentOutcome(EXPIRED_WORTHLESS, "EXPIRED_WORTHLESS", 0.0, "Option expired out of the money.")
        return AssignmentOutcome(ASSIGNED, "ASSIGNED", intrinsic, "Short option finished in the money in paper simulation.")


def _intrinsic(strategy: str, strike: float, price: float) -> float:
    if strategy == COVERED_CALL:
        return round(max(0.0, price - strike), 6)
    if strategy == CASH_SECURED_PUT:
        return round(max(0.0, strike - price), 6)
    raise AssignmentSimulationError(f"Unsupported strategy: {strategy}")


def _positive(value: float, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AssignmentSimulationError(f"{field} must be numeric") from exc
    if number <= 0.0:
        raise AssignmentSimulationError(f"{field} must be positive")
    return number


__all__ = ["AssignmentOutcome", "AssignmentSimulationError", "AssignmentSimulator"]
