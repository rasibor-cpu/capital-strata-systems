from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from backend.options.options_income_strategy_domain import CASH_SECURED_PUT, COVERED_CALL
from backend.options.paper_position_repository import PaperIncomePosition, SAFE_FLAGS


SUPPORTED_INCOME_STRATEGIES = {COVERED_CALL, CASH_SECURED_PUT}


class OptionsIncomeConstraintError(ValueError):
    """Raised when paper options income portfolio constraints fail closed."""


@dataclass(frozen=True)
class OptionsIncomeConstraintConfig:
    max_single_underlying_pct: float = 0.45
    max_single_expiry_pct: float = 0.55
    max_single_strategy_pct: float = 0.70
    max_single_sector_pct: float = 0.65
    max_assignment_concentration_pct: float = 0.55
    max_single_position_pct: float = 0.35
    min_available_capital_pct: float = 0.05


class OptionsIncomeConstraintEngine:
    def __init__(self, config: OptionsIncomeConstraintConfig | None = None) -> None:
        self.config = config or OptionsIncomeConstraintConfig()

    def validate_capital(self, total_capital: Any) -> float:
        capital = _positive(total_capital, "total_capital")
        return capital

    def validate_position(self, position: PaperIncomePosition) -> None:
        if position.strategy_type not in SUPPORTED_INCOME_STRATEGIES:
            raise OptionsIncomeConstraintError(f"Unsupported strategy: {position.strategy_type}")
        if position.collateral_reserved < 0 or position.collateral_released < 0:
            raise OptionsIncomeConstraintError("Invalid collateral")
        if position.premium_received < 0 or position.premium_remaining < 0:
            raise OptionsIncomeConstraintError("Invalid premium")
        _date(position.expiry, "expiry")
        if {**SAFE_FLAGS, **dict(position.advisory_flags or {})} != SAFE_FLAGS:
            raise OptionsIncomeConstraintError("Unsafe advisory flags")

    def validate_candidate(self, candidate: Mapping[str, Any]) -> None:
        if candidate.get("validation_status") != "PASS":
            raise OptionsIncomeConstraintError("Only accepted OI-003 opportunities are allowed")
        if candidate.get("strategy") not in SUPPORTED_INCOME_STRATEGIES:
            raise OptionsIncomeConstraintError(f"Unsupported strategy: {candidate.get('strategy')}")
        if candidate.get("advisory_only") is not True or candidate.get("execution_allowed") is not False:
            raise OptionsIncomeConstraintError("Unsafe opportunity advisory flags")
        if candidate.get("live_trading_blocked") is not True or candidate.get("broker_execution_armed") is not False:
            raise OptionsIncomeConstraintError("Unsafe opportunity broker flags")
        _positive(candidate.get("collateral_required"), "collateral_required")
        _non_negative(candidate.get("total_premium"), "total_premium")
        _date(candidate.get("expiry"), "expiry")

    def validate_allocations(
        self,
        allocations: Sequence[Mapping[str, Any]],
        *,
        total_capital: float,
        sector_by_underlying: Mapping[str, str] | None = None,
    ) -> None:
        capital = self.validate_capital(total_capital)
        seen: set[str] = set()
        for row in allocations:
            allocation_id = str(row.get("allocation_id") or "").strip()
            if not allocation_id:
                raise OptionsIncomeConstraintError("Allocation is missing identifier")
            if allocation_id in seen:
                raise OptionsIncomeConstraintError(f"Duplicate allocation: {allocation_id}")
            seen.add(allocation_id)
            if row.get("strategy") not in SUPPORTED_INCOME_STRATEGIES:
                raise OptionsIncomeConstraintError(f"Unsupported strategy: {row.get('strategy')}")
            collateral = _positive(row.get("collateral"), "collateral")
            if collateral / capital > self.config.max_single_position_pct:
                raise OptionsIncomeConstraintError("Single position concentration violation")
            _date(row.get("expiry"), "expiry")

        used = sum(float(row.get("collateral", 0.0)) for row in allocations)
        if used > capital:
            raise OptionsIncomeConstraintError("Allocated collateral exceeds total capital")
        if allocations and (capital - used) / capital < self.config.min_available_capital_pct:
            raise OptionsIncomeConstraintError("Available capital reserve violation")
        self._validate_group_limit(allocations, "underlying", capital, self.config.max_single_underlying_pct, "single underlying")
        self._validate_group_limit(allocations, "expiry", capital, self.config.max_single_expiry_pct, "single expiry")
        self._validate_group_limit(allocations, "strategy", capital, self.config.max_single_strategy_pct, "single strategy")
        self._validate_assignment_limit(allocations, capital)
        self._validate_sector_limit(allocations, capital, sector_by_underlying or {})

    def _validate_group_limit(self, allocations: Sequence[Mapping[str, Any]], field: str, capital: float, limit: float, label: str) -> None:
        by_group: dict[str, float] = {}
        for row in allocations:
            group = str(row.get(field) or "UNKNOWN").strip().upper()
            by_group[group] = by_group.get(group, 0.0) + float(row.get("collateral", 0.0))
        if any(value / capital > limit for value in by_group.values()):
            raise OptionsIncomeConstraintError(f"{label} concentration violation")

    def _validate_sector_limit(self, allocations: Sequence[Mapping[str, Any]], capital: float, sector_by_underlying: Mapping[str, str]) -> None:
        by_sector: dict[str, float] = {}
        for row in allocations:
            underlying = str(row.get("underlying") or "").strip().upper()
            sector = str(sector_by_underlying.get(underlying, "UNKNOWN")).strip().upper()
            by_sector[sector] = by_sector.get(sector, 0.0) + float(row.get("collateral", 0.0))
        if any(value / capital > self.config.max_single_sector_pct for value in by_sector.values()):
            raise OptionsIncomeConstraintError("sector concentration violation")

    def _validate_assignment_limit(self, allocations: Sequence[Mapping[str, Any]], capital: float) -> None:
        by_underlying: dict[str, float] = {}
        for row in allocations:
            underlying = str(row.get("underlying") or "").strip().upper()
            by_underlying[underlying] = by_underlying.get(underlying, 0.0) + float(row.get("assignment_exposure", row.get("collateral", 0.0)) or 0.0)
        if any(value / capital > self.config.max_assignment_concentration_pct for value in by_underlying.values()):
            raise OptionsIncomeConstraintError("assignment concentration violation")


def _positive(value: Any, field: str) -> float:
    number = _non_negative(value, field)
    if number <= 0.0:
        raise OptionsIncomeConstraintError(f"{field} must be positive")
    return number


def _non_negative(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeConstraintError(f"{field} must be numeric") from exc
    if number < 0.0 or number != number or number in {float("inf"), float("-inf")}:
        raise OptionsIncomeConstraintError(f"{field} must be non-negative finite")
    return number


def _date(value: Any, field: str) -> None:
    try:
        datetime.fromisoformat(str(value or "").strip())
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeConstraintError(f"Invalid {field}") from exc


__all__ = [
    "OptionsIncomeConstraintConfig",
    "OptionsIncomeConstraintEngine",
    "OptionsIncomeConstraintError",
    "SUPPORTED_INCOME_STRATEGIES",
]
