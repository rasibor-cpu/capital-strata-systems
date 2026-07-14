from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

from backend.options.options_income_constraints import SUPPORTED_INCOME_STRATEGIES
from backend.options.paper_position_repository import SAFE_FLAGS


GREEK_FIELDS = ("delta", "gamma", "theta", "vega", "rho")


class OptionsGreeksAggregationError(ValueError):
    """Raised when options Greeks aggregation must fail closed."""


@dataclass(frozen=True)
class OptionsGreeksAggregation:
    status: str
    position_level: list[dict[str, Any]]
    by_underlying: dict[str, dict[str, float]]
    by_strategy: dict[str, dict[str, float]]
    by_expiry: dict[str, dict[str, float]]
    portfolio: dict[str, Any]
    unavailable: list[str]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "position_level": self.position_level,
            "by_underlying": self.by_underlying,
            "by_strategy": self.by_strategy,
            "by_expiry": self.by_expiry,
            "portfolio": self.portfolio,
            "unavailable": self.unavailable,
            **SAFE_FLAGS,
        }


class OptionsGreeksAggregator:
    def aggregate(
        self,
        portfolio: Mapping[str, Any],
        *,
        greeks_by_symbol: Mapping[str, Mapping[str, Any]] | None,
        total_capital: float | None = None,
    ) -> OptionsGreeksAggregation:
        allocations = _allocations(portfolio)
        capital = _positive(total_capital if total_capital is not None else portfolio.get("capital", {}).get("allocated_capital", 0.0), "total_capital")
        if greeks_by_symbol is None:
            greeks_by_symbol = {}
        positions: list[dict[str, Any]] = []
        unavailable: list[str] = []
        for row in allocations:
            symbol = str(row.get("option_symbol") or "").strip()
            if not symbol:
                raise OptionsGreeksAggregationError("Allocation missing option symbol")
            strategy = str(row.get("strategy") or "").strip().upper()
            if strategy not in SUPPORTED_INCOME_STRATEGIES:
                raise OptionsGreeksAggregationError(f"Unsupported strategy: {strategy}")
            raw = greeks_by_symbol.get(symbol)
            if raw is None:
                unavailable.append(symbol)
                continue
            greeks = {field: _finite(raw.get(field), field) for field in GREEK_FIELDS}
            contracts = max(1.0, float(row.get("contracts", 1.0) or 1.0))
            multiplier = max(1.0, float(row.get("multiplier", 100.0) or 100.0))
            sign = -1.0
            contribution = {field: round(greeks[field] * contracts * multiplier * sign, 8) for field in GREEK_FIELDS}
            collateral = _non_negative(row.get("collateral", 0.0), "collateral")
            positions.append(
                {
                    "allocation_id": row.get("allocation_id", symbol),
                    "option_symbol": symbol,
                    "underlying": str(row.get("underlying") or "UNKNOWN").upper(),
                    "strategy": strategy,
                    "expiry": str(row.get("expiry") or "UNKNOWN"),
                    "collateral": collateral,
                    **contribution,
                    "absolute_delta_exposure": round(abs(contribution["delta"]), 8),
                    "greeks_per_unit_collateral": _per_unit(contribution, collateral),
                    "greeks_per_unit_capital": _per_unit(contribution, capital),
                    **SAFE_FLAGS,
                }
            )
        by_underlying = _group(positions, "underlying")
        by_strategy = _group(positions, "strategy")
        by_expiry = _group(positions, "expiry")
        totals = _sum(positions)
        totals.update(
            {
                "absolute_delta_exposure": round(sum(abs(row["delta"]) for row in positions), 8),
                "net_directional_exposure": round(totals["delta"], 8),
                "theta_income": round(totals["theta"], 8),
                "vega_exposure": round(abs(totals["vega"]), 8),
                "gamma_concentration": _max_abs(by_underlying, "gamma"),
                "covered_call_delta": round(sum(row["delta"] for row in positions if row["strategy"] == "COVERED_CALL"), 8),
                "cash_secured_put_delta": round(sum(row["delta"] for row in positions if row["strategy"] == "CASH_SECURED_PUT"), 8),
                "greeks_per_unit_collateral": _per_unit(totals, sum(row["collateral"] for row in positions)),
                "greeks_per_unit_capital": _per_unit(totals, capital),
            }
        )
        status = "UNAVAILABLE" if unavailable else "GREEN"
        return OptionsGreeksAggregation(status, positions, by_underlying, by_strategy, by_expiry, totals, sorted(unavailable))


def _allocations(portfolio: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(portfolio, Mapping):
        raise OptionsGreeksAggregationError("Missing portfolio")
    rows = portfolio.get("allocations")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise OptionsGreeksAggregationError("Portfolio allocations must be a sequence")
    return [dict(row) for row in rows]


def _group(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(field) or "UNKNOWN"), []).append(row)
    return {key: _sum(grouped[key]) for key in sorted(grouped)}


def _sum(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    return {field: round(sum(float(row.get(field, 0.0) or 0.0) for row in rows), 8) for field in GREEK_FIELDS}


def _per_unit(greeks: Mapping[str, Any], divisor: float) -> dict[str, float]:
    if divisor <= 0.0:
        return {field: 0.0 for field in GREEK_FIELDS}
    return {field: round(float(greeks.get(field, 0.0) or 0.0) / divisor, 10) for field in GREEK_FIELDS}


def _max_abs(grouped: Mapping[str, Mapping[str, Any]], field: str) -> float:
    return round(max([0.0, *[abs(float(row.get(field, 0.0) or 0.0)) for row in grouped.values()]]), 8)


def _finite(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsGreeksAggregationError(f"Invalid Greek: {field}") from exc
    if not isfinite(number):
        raise OptionsGreeksAggregationError(f"Invalid Greek: {field}")
    return number


def _positive(value: Any, field: str) -> float:
    number = _non_negative(value, field)
    if number <= 0.0:
        raise OptionsGreeksAggregationError(f"{field} must be positive")
    return number


def _non_negative(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsGreeksAggregationError(f"{field} must be numeric") from exc
    if not isfinite(number) or number < 0.0:
        raise OptionsGreeksAggregationError(f"{field} must be non-negative finite")
    return number


__all__ = ["GREEK_FIELDS", "OptionsGreeksAggregation", "OptionsGreeksAggregationError", "OptionsGreeksAggregator"]
