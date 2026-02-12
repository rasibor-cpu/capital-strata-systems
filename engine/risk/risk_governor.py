"""
Capital Strata Systems
Risk Governor – Adaptive Portfolio Governance

Live capital-aware risk enforcement layer.
Includes adaptive portfolio cap scaling.
Fail-closed by design.
"""

from __future__ import annotations

from typing import Dict, Any


class RiskGovernor:

    # --------------------------------------------------------
    # Initialization
    # --------------------------------------------------------

    def __init__(self) -> None:
        self.policy = "live"

        # Static hard protections
        self.max_drawdown_pct = 0.05          # 5% global shutdown
        self.max_trades_per_day = 20
        self.max_portfolio_risk_pct = 0.08    # Base ceiling (pre-adaptive)

        # Daily tracking
        self.trades_today = 0

    # --------------------------------------------------------
    # Adaptive Portfolio Cap
    # --------------------------------------------------------

    def _adaptive_portfolio_cap(self, drawdown: float) -> float:
        """
        Tightens portfolio risk cap as drawdown increases.
        """

        if drawdown >= 0.04:
            return 0.04  # 4%
        elif drawdown >= 0.02:
            return 0.06  # 6%
        else:
            return 0.08  # 8%

    # --------------------------------------------------------
    # Main Evaluation
    # --------------------------------------------------------

    def evaluate(
        self,
        *,
        instrument: str,
        equity: float,
        trade_risk: float,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        equity_peak = float(state.get("equity_peak", equity))
        open_futures_risk = float(state.get("open_futures_risk", 0.0))
        open_fx_risk = float(state.get("open_fx_risk", 0.0))
        open_equities_risk = float(state.get("open_equities_risk", 0.0))
        open_crypto_risk = float(state.get("open_crypto_risk", 0.0))
        open_rates_risk = float(state.get("open_rates_risk", 0.0))

        # ----------------------------------------------------
        # 1. Global Drawdown Check
        # ----------------------------------------------------

        drawdown = 0.0
        if equity_peak > 0:
            drawdown = (equity_peak - equity) / equity_peak

        if drawdown >= self.max_drawdown_pct:
            return {
                "decision": "BLOCK",
                "policy": self.policy,
                "reasons": ["GLOBAL_DRAWDOWN_LIMIT"],
                "drawdown": round(drawdown, 6),
            }

        # ----------------------------------------------------
        # 2. Trade Throttle
        # ----------------------------------------------------

        if self.trades_today >= self.max_trades_per_day:
            return {
                "decision": "BLOCK",
                "policy": self.policy,
                "reasons": ["TRADE_LIMIT_REACHED"],
            }

        # ----------------------------------------------------
        # 3. Portfolio Exposure Calculation
        # ----------------------------------------------------

        total_open_risk = (
            open_futures_risk
            + open_fx_risk
            + open_equities_risk
            + open_crypto_risk
            + open_rates_risk
        )

        portfolio_total_risk = total_open_risk + trade_risk

        allocation_pct = 0.0
        if equity > 0:
            allocation_pct = portfolio_total_risk / equity

        adaptive_cap = self._adaptive_portfolio_cap(drawdown)

        if allocation_pct > adaptive_cap:
            return {
                "decision": "BLOCK",
                "policy": self.policy,
                "reasons": [
                    "PORTFOLIO_RISK_CAP_EXCEEDED",
                    f"allocation {allocation_pct:.2%} > cap {adaptive_cap:.2%}",
                ],
                "portfolio_allocation_pct": round(allocation_pct, 6),
                "portfolio_total_risk": round(portfolio_total_risk, 6),
                "adaptive_cap": adaptive_cap,
                "drawdown": round(drawdown, 6),
            }

        # ----------------------------------------------------
        # APPROVED
        # ----------------------------------------------------

        return {
            "decision": "ALLOW",
            "policy": self.policy,
            "portfolio_allocation_pct": round(allocation_pct, 6),
            "portfolio_total_risk": round(portfolio_total_risk, 6),
            "adaptive_cap": adaptive_cap,
            "drawdown": round(drawdown, 6),
        }
