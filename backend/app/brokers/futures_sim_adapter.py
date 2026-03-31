"""
Futures Simulation Adapter
Capital Strata Systems – Phase 17 (Spec-Aligned)

Enhancements:
- Uses contract spec engine (no hardcoded risk)
- Symbol-aware risk calculation
- Preserves portfolio allocation enforcement
- Fully backward compatible
"""

from typing import Dict

from backend.app.global_futures_store import load_exposure, save_exposure
from backend.app.risk.futures_contract_specs import calculate_futures_risk


class FuturesSimAdapter:

    def __init__(self, max_portfolio_allocation: float = 0.03):
        """
        max_portfolio_allocation = max % of total equity
        allowed for total futures exposure (default 3%)
        """
        self.max_allocation = float(max_portfolio_allocation)
        self.open_futures_risk = load_exposure()

    # -----------------------------------------------------

    def _calculate_contract_risk(
        self,
        symbol: str,
        entry_price: float,
        stop_price: float,
        contracts: int,
    ) -> float:
        """
        Delegates to contract spec engine (symbol-aware).
        """
        return calculate_futures_risk(
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop_price,
            contracts=contracts,
        )

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

        # ---- Calculate symbol-aware risk ----
        trade_risk = self._calculate_contract_risk(
            symbol,
            entry_price,
            stop_price,
            contracts,
        )

        total_future_risk = self.open_futures_risk + trade_risk
        allocation_pct = total_future_risk / max(current_equity, 1e-9)

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
            self.open_futures_risk - float(risk_reduction)
        )
        save_exposure(self.open_futures_risk)