from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from backend.options.options_income_strategy_domain import CASH_SECURED_PUT, COVERED_CALL
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeAssignmentRiskError(ValueError):
    """Raised when assignment risk cannot be calculated."""


@dataclass(frozen=True)
class AssignmentRiskReport:
    contracts_exposed: int
    shares_potentially_called_away: float
    cash_potentially_required: float
    assignment_notional: float
    assignment_concentration: dict[str, float]
    itm_exposure: float
    near_expiry_exposure: float
    underlying_concentration: dict[str, float]
    expiry_concentration: dict[str, float]
    portfolio_assignment_ratio: float
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, **SAFE_FLAGS}


class OptionsIncomeAssignmentRiskAnalyzer:
    def analyze(self, portfolio: Mapping[str, Any], *, market_data_by_underlying: Mapping[str, Mapping[str, Any]] | None = None) -> AssignmentRiskReport:
        rows = list(portfolio.get("allocations", []) or [])
        capital = float(portfolio.get("capital", {}).get("allocated_capital", 0.0) or 0.0)
        market = market_data_by_underlying or {}
        contracts = 0
        shares_called = 0.0
        cash_required = 0.0
        by_underlying: dict[str, float] = {}
        by_expiry: dict[str, float] = {}
        itm = 0.0
        near_expiry = 0.0
        for row in rows:
            strategy = str(row.get("strategy") or "").upper()
            if strategy not in {COVERED_CALL, CASH_SECURED_PUT}:
                raise OptionsIncomeAssignmentRiskError(f"Unsupported strategy: {strategy}")
            contract_count = int(row.get("contracts", 1) or 1)
            multiplier = float(row.get("multiplier", 100.0) or 100.0)
            notional = float(row.get("assignment_exposure", row.get("collateral", 0.0)) or 0.0)
            if notional < 0.0:
                raise OptionsIncomeAssignmentRiskError("assignment exposure cannot be negative")
            contracts += contract_count
            if strategy == COVERED_CALL:
                shares_called += contract_count * multiplier
            else:
                cash_required += notional
            underlying = str(row.get("underlying") or "UNKNOWN").upper()
            expiry = str(row.get("expiry") or "UNKNOWN")
            by_underlying[underlying] = by_underlying.get(underlying, 0.0) + notional
            by_expiry[expiry] = by_expiry.get(expiry, 0.0) + notional
            spot = market.get(underlying, {}).get("underlying_price")
            if spot is not None:
                price = float(spot)
                strike = float(row.get("strike", 0.0) or 0.0)
                if (strategy == COVERED_CALL and price > strike) or (strategy == CASH_SECURED_PUT and price < strike):
                    itm += notional
            if str(row.get("expiry", "")) <= str(market.get(underlying, {}).get("near_expiry_cutoff", "")):
                near_expiry += notional
        total = sum(by_underlying.values())
        concentration = {key: round(value / total, 8) for key, value in sorted(by_underlying.items())} if total > 0 else {}
        expiry_concentration = {key: round(value / total, 8) for key, value in sorted(by_expiry.items())} if total > 0 else {}
        return AssignmentRiskReport(
            contracts_exposed=contracts,
            shares_potentially_called_away=round(shares_called, 6),
            cash_potentially_required=round(cash_required, 6),
            assignment_notional=round(total, 6),
            assignment_concentration=concentration,
            itm_exposure=round(itm, 6),
            near_expiry_exposure=round(near_expiry, 6),
            underlying_concentration=concentration,
            expiry_concentration=expiry_concentration,
            portfolio_assignment_ratio=round((total / capital) if capital > 0 else 0.0, 8),
        )


__all__ = ["AssignmentRiskReport", "OptionsIncomeAssignmentRiskAnalyzer", "OptionsIncomeAssignmentRiskError"]
