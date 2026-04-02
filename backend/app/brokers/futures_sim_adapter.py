"""
Futures Simulation Adapter
Capital Strata Systems – Phase 17 (Spec-Aligned)

Enhancements:
- Uses contract spec engine (no hardcoded risk)
- Symbol-aware risk calculation
- Preserves portfolio allocation enforcement
- Fully backward compatible
- Tuned for small-account futures simulation
"""

from typing import Dict

from backend.app.global_futures_store import load_exposure, save_exposure
from backend.app.risk.futures_contract_specs import calculate_futures_risk


class FuturesSimAdapter:

    def __init__(self, max_portfolio_allocation: float = 5.00):
        """
        max_portfolio_allocation = max fraction of total equity
        allowed for total futures exposure.

        Examples:
        - 0.03 = 3%
        - 1.00 = 100%
        - 5.00 = 500%

        Default is intentionally higher for leveraged futures simulation
        on small test accounts.
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

        equity = max(float(current_equity), 1e-9)
        total_future_risk = float(self.open_futures_risk) + float(trade_risk)
        allocation_pct = total_future_risk / equity

        # ---- Optional tiny-account safety floor ----
        # If equity is extremely small, avoid impossible approvals
        # while still allowing realistic leveraged simulation.
        effective_cap = float(self.max_allocation)
        if equity <= 500:
            effective_cap = max(effective_cap, 5.0)

        # ---- Portfolio allocation enforcement ----
        if allocation_pct > effective_cap:
            return {
                "status": "REJECTED",
                "reason": f"Portfolio futures allocation {allocation_pct:.2%} exceeds {effective_cap:.2%}",
                "symbol": symbol,
                "trade_risk": float(trade_risk),
                "current_open_risk": float(self.open_futures_risk),
                "equity": equity,
                "max_allocation": effective_cap,
            }

        # ---- Approve trade ----
        self.open_futures_risk = total_future_risk
        save_exposure(self.open_futures_risk)

        return {
            "status": "APPROVED",
            "symbol": symbol,
            "contracts": int(contracts),
            "trade_risk": float(trade_risk),
            "total_futures_risk": float(self.open_futures_risk),
            "allocation_pct": round(allocation_pct, 6),
            "max_allocation": effective_cap,
        }

    # -----------------------------------------------------

    def close_trade(self, risk_reduction: float):
        """
        Reduces open futures risk when trade closes
        """
        self.open_futures_risk = max(
            0.0,
            float(self.open_futures_risk) - float(risk_reduction)
        )
        save_exposure(self.open_futures_risk)