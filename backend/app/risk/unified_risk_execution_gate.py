from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from backend.app.risk.portfolio_governor import PortfolioGovernor
from backend.app.risk.capital_allocation_governor import CapitalAllocationGovernor


@dataclass(frozen=True)
class UnifiedRiskGateDecision:
    approved: bool
    asset_class: str
    symbol: str
    mode: str
    reason: str
    portfolio_reason: str
    capital_reason: str
    approved_allocation: float


class UnifiedRiskExecutionGate:
    """
    Institutional unified risk gate.

    PCNRASS SAFE:
    - Governance only
    - No broker calls
    - No order placement
    - Must approve before execution orchestration
    """

    def __init__(self) -> None:
        self.portfolio_governor = PortfolioGovernor()
        self.capital_governor = CapitalAllocationGovernor()

    def evaluate(
        self,
        *,
        asset_class: str,
        symbol: str,
        requested_exposure: float,
        requested_allocation: float,
        current_portfolio_exposure: float,
        account_equity: float,
        available_capital: float,
        mode: str,
    ) -> UnifiedRiskGateDecision:

        portfolio_decision = self.portfolio_governor.evaluate(
            asset_class=asset_class,
            symbol=symbol,
            requested_exposure=requested_exposure,
            current_portfolio_exposure=current_portfolio_exposure,
            account_equity=account_equity,
            mode=mode,
        )

        if not portfolio_decision.approved:
            return UnifiedRiskGateDecision(
                approved=False,
                asset_class=str(asset_class).upper(),
                symbol=str(symbol).upper(),
                mode=str(mode).lower(),
                reason="PORTFOLIO_GOVERNOR_BLOCK",
                portfolio_reason=portfolio_decision.reason,
                capital_reason="NOT_EVALUATED",
                approved_allocation=0.0,
            )

        capital_decision = self.capital_governor.evaluate(
            asset_class=asset_class,
            symbol=symbol,
            requested_allocation=requested_allocation,
            available_capital=available_capital,
            mode=mode,
        )

        if not capital_decision.approved:
            return UnifiedRiskGateDecision(
                approved=False,
                asset_class=str(asset_class).upper(),
                symbol=str(symbol).upper(),
                mode=str(mode).lower(),
                reason="CAPITAL_GOVERNOR_BLOCK",
                portfolio_reason=portfolio_decision.reason,
                capital_reason=capital_decision.reason,
                approved_allocation=capital_decision.approved_allocation,
            )

        return UnifiedRiskGateDecision(
            approved=True,
            asset_class=str(asset_class).upper(),
            symbol=str(symbol).upper(),
            mode=str(mode).lower(),
            reason="UNIFIED_RISK_GATE_APPROVED",
            portfolio_reason=portfolio_decision.reason,
            capital_reason=capital_decision.reason,
            approved_allocation=capital_decision.approved_allocation,
        )

    def decision_to_dict(self, decision: UnifiedRiskGateDecision) -> Dict[str, Any]:
        return {
            "approved": decision.approved,
            "asset_class": decision.asset_class,
            "symbol": decision.symbol,
            "mode": decision.mode,
            "reason": decision.reason,
            "portfolio_reason": decision.portfolio_reason,
            "capital_reason": decision.capital_reason,
            "approved_allocation": decision.approved_allocation,
        }
