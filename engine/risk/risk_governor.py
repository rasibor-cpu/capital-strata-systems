"""
Capital Strata Systems
Risk Governor – Adaptive Portfolio + Position Scaling

Features:
- Equity peak persistence
- Drawdown tracking
- Adaptive portfolio cap
- Adaptive position size multiplier
"""

from __future__ import annotations

from typing import Dict, Any


class RiskGovernor:

    def __init__(self) -> None:
        self.policy = "live"

        self.max_drawdown_pct = 0.05
        self.max_trades_per_day = 20
        self.base_portfolio_cap = 0.08

        self.trades_today = 0

    # --------------------------------------------------------
    # Adaptive Portfolio Cap
    # --------------------------------------------------------

    def _adaptive_portfolio_cap(self, drawdown: float) -> float:
        if drawdown >= 0.04:
            return 0.04
        elif drawdown >= 0.02:
            return 0.06
        return 0.08

    # --------------------------------------------------------
    # Adaptive Position Multiplier
    # --------------------------------------------------------

    def _risk_multiplier(self, drawdown: float) -> float:
        if drawdown >= 0.04:
            return 0.5
        elif drawdown >= 0.02:
            return 0.75
        return 1.0

    # --------------------------------------------------------
    # Evaluation
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

        if equity > equity_peak:
            equity_peak = equity

        state["equity_peak"] = equity_peak

        drawdown = 0.0
        if equity_peak > 0:
            drawdown = (equity_peak - equity) / equity_peak

        state["current_drawdown"] = drawdown

        if drawdown >= self.max_drawdown_pct:
            return {
                "decision": "BLOCK",
                "policy": self.policy,
                "reasons": ["GLOBAL_DRAWDOWN_LIMIT"],
                "drawdown": round(drawdown, 6),
            }

        if self.trades_today >= self.max_trades_per_day:
            return {
                "decision": "BLOCK",
                "policy": self.policy,
                "reasons": ["TRADE_LIMIT_REACHED"],
            }

        # -----------------------------------------
        # Adaptive Trade Scaling
        # -----------------------------------------

        multiplier = self._risk_multiplier(drawdown)
        effective_trade_risk = trade_risk * multiplier

        state["risk_multiplier"] = multiplier

        # -----------------------------------------
        # Portfolio Risk Calculation
        # -----------------------------------------

        open_futures_risk = float(state.get("open_futures_risk", 0.0))
        open_fx_risk = float(state.get("open_fx_risk", 0.0))
        open_equities_risk = float(state.get("open_equities_risk", 0.0))
        open_crypto_risk = float(state.get("open_crypto_risk", 0.0))
        open_rates_risk = float(state.get("open_rates_risk", 0.0))

        total_open_risk = (
            open_futures_risk
            + open_fx_risk
            + open_equities_risk
            + open_crypto_risk
            + open_rates_risk
        )

        portfolio_total_risk = total_open_risk + effective_trade_risk

        allocation_pct = 0.0
        if equity > 0:
            allocation_pct = portfolio_total_risk / equity

        adaptive_cap = self._adaptive_portfolio_cap(drawdown)
        state["adaptive_portfolio_cap"] = adaptive_cap

        if allocation_pct > adaptive_cap:
            return {
                "decision": "BLOCK",
                "policy": self.policy,
                "reasons": [
                    "PORTFOLIO_RISK_CAP_EXCEEDED",
                    f"{allocation_pct:.2%} > {adaptive_cap:.2%}",
                ],
                "portfolio_allocation_pct": round(allocation_pct, 6),
                "portfolio_total_risk": round(portfolio_total_risk, 6),
                "adaptive_cap": adaptive_cap,
                "risk_multiplier": multiplier,
                "drawdown": round(drawdown, 6),
            }

        return {
            "decision": "ALLOW",
            "policy": self.policy,
            "portfolio_allocation_pct": round(allocation_pct, 6),
            "portfolio_total_risk": round(portfolio_total_risk, 6),
            "adaptive_cap": adaptive_cap,
            "risk_multiplier": multiplier,
            "drawdown": round(drawdown, 6),
        }
