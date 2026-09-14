from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from backend.allocation.caie_shadow_adapter import CAIEShadowAdapter
from backend.allocation.opportunity_proposal import OpportunityProposal


def build_caie_shadow_runtime_projection(
    proposals: Iterable[OpportunityProposal],
    *,
    trade_eligible: bool,
    available_capital: Decimal,
    asset_class_caps: Mapping[str, Decimal],
    broker_caps: Mapping[str, Decimal],
    concentration_cap: Decimal = Decimal("0.25"),
) -> dict:
    """Read-only runtime projection for CAIE shadow recommendations."""

    result = CAIEShadowAdapter.evaluate(
        proposals,
        trade_eligible=trade_eligible,
        available_capital=available_capital,
        asset_class_caps=asset_class_caps,
        broker_caps=broker_caps,
        concentration_cap=concentration_cap,
    )

    allocations = []
    if result.plan is not None:
        allocations = [
            {
                "proposal_id": item.proposal_id,
                "broker": item.broker,
                "asset_class": item.asset_class,
                "symbol": item.symbol,
                "score": format(item.score, "f"),
                "requested_capital": format(item.requested_capital, "f"),
                "allocated_capital": format(item.allocated_capital, "f"),
                "concentration_limited": item.concentration_limited,
            }
            for item in result.plan.allocations
        ]

    return {
        "schema_version": "css.caie.shadow-runtime.v1",
        "status": result.status,
        "reason": result.reason,
        "trade_eligible": trade_eligible,
        "allocations": allocations,
        "deployed_capital": (
            format(result.plan.deployed_capital, "f")
            if result.plan is not None
            else "0"
        ),
        "remaining_cash": (
            format(result.plan.remaining_cash, "f")
            if result.plan is not None
            else format(available_capital, "f")
        ),
        "execution_allowed": False,
        "broker_execution_armed": False,
        "money_movement_allowed": False,
        "live_trading_authorized": False,
        "mode": "SHADOW_ONLY",
    }
