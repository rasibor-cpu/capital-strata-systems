from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class CapitalAllocationDecision:
    approved: bool
    asset_class: str
    symbol: str
    requested_allocation: float
    approved_allocation: float
    available_capital: float
    reason: str
    mode: str


class CapitalAllocationGovernor:
    """
    Institutional capital allocation authority.

    PCNRASS SAFE:
    - Governance only
    - No broker calls
    - No order placement
    - Capital sizing authority
    """

    DEFAULT_MAX_SINGLE_TRADE_ALLOCATION_PCT = 0.05

    DEFAULT_MAX_ALLOCATION_BY_ASSET_CLASS: Dict[str, float] = {
        "CRYPTO": 0.05,
        "FX": 0.05,
        "FUTURES": 0.02,
        "OPTIONS": 0.02,
    }

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        *,
        asset_class: str,
        symbol: str,
        requested_allocation: float,
        available_capital: float,
        mode: str,
    ) -> CapitalAllocationDecision:

        normalized_asset = str(asset_class or "").strip().upper()

        capital = float(available_capital or 0.0)
        request = float(requested_allocation or 0.0)

        if capital <= 0.0:
            return CapitalAllocationDecision(
                approved=False,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                requested_allocation=request,
                approved_allocation=0.0,
                available_capital=capital,
                reason="NO_AVAILABLE_CAPITAL",
                mode=str(mode).lower(),
            )

        if request <= 0.0:
            return CapitalAllocationDecision(
                approved=False,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                requested_allocation=request,
                approved_allocation=0.0,
                available_capital=capital,
                reason="INVALID_REQUESTED_ALLOCATION",
                mode=str(mode).lower(),
            )

        global_cap = (
            capital
            * self.DEFAULT_MAX_SINGLE_TRADE_ALLOCATION_PCT
        )

        if request > global_cap:

            return CapitalAllocationDecision(
                approved=False,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                requested_allocation=request,
                approved_allocation=global_cap,
                available_capital=capital,
                reason="GLOBAL_SINGLE_TRADE_CAP_EXCEEDED",
                mode=str(mode).lower(),
            )

        asset_cap_pct = self.DEFAULT_MAX_ALLOCATION_BY_ASSET_CLASS.get(
            normalized_asset,
            0.0,
        )

        if asset_cap_pct <= 0.0:

            return CapitalAllocationDecision(
                approved=False,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                requested_allocation=request,
                approved_allocation=0.0,
                available_capital=capital,
                reason="UNKNOWN_OR_UNSUPPORTED_ASSET_CLASS",
                mode=str(mode).lower(),
            )

        asset_cap = capital * asset_cap_pct

        if request > asset_cap:

            return CapitalAllocationDecision(
                approved=False,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                requested_allocation=request,
                approved_allocation=asset_cap,
                available_capital=capital,
                reason="ASSET_CLASS_CAPITAL_LIMIT_EXCEEDED",
                mode=str(mode).lower(),
            )

        return CapitalAllocationDecision(
            approved=True,
            asset_class=normalized_asset,
            symbol=str(symbol).upper(),
            requested_allocation=request,
            approved_allocation=request,
            available_capital=capital,
            reason="CAPITAL_ALLOCATION_APPROVED",
            mode=str(mode).lower(),
        )

    def decision_to_dict(
        self,
        decision: CapitalAllocationDecision,
    ) -> Dict[str, Any]:

        return {
            "approved": decision.approved,
            "asset_class": decision.asset_class,
            "symbol": decision.symbol,
            "requested_allocation": (
                decision.requested_allocation
            ),
            "approved_allocation": (
                decision.approved_allocation
            ),
            "available_capital": (
                decision.available_capital
            ),
            "reason": decision.reason,
            "mode": decision.mode,
        }
