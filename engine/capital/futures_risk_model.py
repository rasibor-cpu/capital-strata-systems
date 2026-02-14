"""
Futures Risk Model – Phase 2C
Capital Strata Systems

Purpose:
- Deterministic futures position sizing
- Contract multiplier aware
- Tick value aware
- Capital bucket compliant
- Pure python / stdlib only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FuturesContractSpec:
    symbol: str
    contract_multiplier: float
    tick_size: float
    tick_value: float
    initial_margin: float


@dataclass(frozen=True)
class FuturesSizingResult:
    contracts: int
    notional_value: float
    margin_required: float
    risk_per_contract: float
    total_risk: float
    bucket_utilization_pct: float
    ok: bool
    reason: str


class FuturesRiskModel:
    """
    Deterministic sizing engine for futures.
    """

    def size_position(
        self,
        *,
        equity: float,
        risk_pct: float,
        stop_distance_points: float,
        contract: FuturesContractSpec,
        futures_capital_bucket: float,   # absolute $ allowed for futures
    ) -> FuturesSizingResult:

        if equity <= 0:
            return self._fail("invalid_equity")

        if risk_pct <= 0:
            return self._fail("invalid_risk_pct")

        if stop_distance_points <= 0:
            return self._fail("invalid_stop_distance")

        # absolute risk allowed
        risk_budget = equity * (risk_pct / 100.0)

        # risk per contract
        ticks = stop_distance_points / contract.tick_size
        risk_per_contract = ticks * contract.tick_value

        if risk_per_contract <= 0:
            return self._fail("invalid_contract_spec")

        contracts = int(risk_budget // risk_per_contract)

        if contracts <= 0:
            return self._fail("risk_too_small_for_one_contract")

        notional_value = contracts * contract.contract_multiplier
        margin_required = contracts * contract.initial_margin
        total_risk = contracts * risk_per_contract

        if margin_required > futures_capital_bucket:
            return self._fail("exceeds_futures_bucket")

        bucket_util = margin_required / futures_capital_bucket

        return FuturesSizingResult(
            contracts=contracts,
            notional_value=notional_value,
            margin_required=margin_required,
            risk_per_contract=risk_per_contract,
            total_risk=total_risk,
            bucket_utilization_pct=bucket_util,
            ok=True,
            reason="ok",
        )

    def _fail(self, reason: str) -> FuturesSizingResult:
        return FuturesSizingResult(
            contracts=0,
            notional_value=0.0,
            margin_required=0.0,
            risk_per_contract=0.0,
            total_risk=0.0,
            bucket_utilization_pct=0.0,
            ok=False,
            reason=reason,
        )
