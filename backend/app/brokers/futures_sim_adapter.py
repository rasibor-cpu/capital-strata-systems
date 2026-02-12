"""
Futures Simulation Adapter
Capital Strata Systems – Phase 16 (Persistent Exposure)

Simulates futures contract risk
with portfolio allocation enforcement
and persistent exposure tracking.
"""

from typing import Dict
from backend.app.global_futures_store import load_exposure, save_exposure


class FuturesSimAdapter:

    def __init__(self, max_portfolio_allocation: float = 0.03):
        """
        max_portfolio_allocation = max % of total equity
        allowed for total futures exposure (default 3%)
        """
        self.max_allocation = max_portfolio_allocation
        self.open_futures_risk = load_exposure()

    # -----------------------------------------------------

    def _calculate_contract_risk(
        self,
        entry_price: float,
        stop_price: float,
        contracts: int,
        point_value: float = 50.0,
    ) -> float:
        """
        Example: ES = $50 per point
        """
        risk_per_contract = abs(entry_price - stop_price) * point_value
        return risk_per_contract * contracts

    # -----------------------------------------------------

    def simulate_trade(
        self,
        *,
        symbol: str,
        entry_price: float,
        stop_price: float,
        contracts: int,
        current_equity: float,
        state: Dict,
    ) -> Dict:

        trade_risk = self._calculate_contract_risk(
            entry_price,
            stop_price,
            contracts,
        )

        total_future_risk = self.open_futures_risk + trade_risk
        allocation_pct = total_future_risk / current_equity

        # ---- Portfolio allocation enforcement ----
        if allocation_pct > self.max_allocation:
            return {
                "status": "REJECTED",
                "reason": f"Portfolio futures allocation {allocation_pct:.2%} exceeds {self.max_allocation:.2%}",
                "symbol": symbol,
                "trade_risk": trade_risk,
                "current_open_risk": self.open_futures_risk,
            }

        # ---- Approve trade ----
        self.open_futures_risk = total_future_risk
        save_exposure(self.open_futures_risk)

        return {
            "status": "APPROVED",
            "symbol": symbol,
            "contracts": contracts,
            "trade_risk": trade_risk,
            "total_futures_risk": self.open_futures_risk,
            "allocation_pct": round(allocation_pct, 6),
        }

    # -----------------------------------------------------

    def close_trade(self, risk_reduction: float):
        """
        Reduces open futures risk when trade closes
        """
        self.open_futures_risk = max(
            0.0,
            self.open_futures_risk - risk_reduction
        )
        save_exposure(self.open_futures_risk)
