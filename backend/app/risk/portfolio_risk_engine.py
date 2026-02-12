"""
Portfolio Risk Engine
Capital Strata Systems – Phase 15

Enforces futures allocation cap
within overall global drawdown architecture.
"""

from typing import Dict, Any
from engine.risk.risk_governor import RiskGovernor


class PortfolioRiskEngine:

    def __init__(self):
        self.risk_governor = RiskGovernor()

        # 3% futures allocation cap
        self.futures_allocation_cap = 0.03

    # --------------------------------------------------

    def evaluate_futures_trade(
        self,
        current_equity: float,
        open_futures_risk: float,
        new_trade_risk: float,
    ) -> Dict[str, Any]:

        if current_equity <= 0:
            return {
                "decision": "BLOCK",
                "reason": "Invalid equity"
            }

        total_futures_risk = open_futures_risk + new_trade_risk

        allocation_pct = total_futures_risk / current_equity

        if allocation_pct > self.futures_allocation_cap:
            return {
                "decision": "BLOCK",
                "reason": f"Futures allocation cap exceeded: "
                          f"{round(allocation_pct*100, 2)}% > "
                          f"{self.futures_allocation_cap*100:.2f}%"
            }

        return {
            "decision": "ALLOW",
            "allocation_pct": round(allocation_pct, 4),
        }
