"""
Capital Strata Systems
Risk Governor – Portfolio-Aware (Fail-Closed)

Now enforces:
1. Global drawdown cap
2. Trade throttle
3. Daily trade limit
4. Portfolio risk cap (cross-asset)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.risk.portfolio_risk_engine import PortfolioRiskEngine


class RiskGovernor:

    def __init__(self):

        # ----------------------------
        # Core risk parameters
        # ----------------------------

        self.global_dd_limit = 0.05          # 5% global drawdown
        self.global_throttle_limit = 0.03    # 3% per-trade throttle
        self.max_portfolio_risk_pct = 0.08   # 8% total portfolio allocation cap

        self.max_trades_per_day = 20

        # ----------------------------
        # Runtime state
        # ----------------------------

        self.trades_today = 0
        self.equity_peak = 0.0

        # Portfolio risk engine
        self.portfolio_engine = PortfolioRiskEngine()

    # ==========================================================
    # CORE EVALUATION
    # ==========================================================

    def evaluate(
        self,
        *,
        instrument: str,
        equity: float,
        trade_risk: float,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        # ----------------------------
        # Track equity peak
        # ----------------------------

        if equity > self.equity_peak:
            self.equity_peak = equity

        # ----------------------------
        # 1. Global drawdown
        # ----------------------------

        if self.equity_peak > 0:
            drawdown = (self.equity_peak - equity) / self.equity_peak
            if drawdown >= self.global_dd_limit:
                return {
                    "decision": "BLOCK",
                    "reason": "GLOBAL_DRAWDOWN_LIMIT",
                    "drawdown_pct": round(drawdown, 6),
                }

        # ----------------------------
        # 2. Per-trade throttle
        # ----------------------------

        if equity > 0:
            trade_pct = trade_risk / equity
            if trade_pct >= self.global_throttle_limit:
                return {
                    "decision": "BLOCK",
                    "reason": "TRADE_RISK_TOO_LARGE",
                    "trade_pct": round(trade_pct, 6),
                }

        # ----------------------------
        # 3. Daily trade limit
        # ----------------------------

        if self.trades_today >= self.max_trades_per_day:
            return {
                "decision": "BLOCK",
                "reason": "TRADE_LIMIT_REACHED",
            }

        # ----------------------------
        # 4. Portfolio risk cap
        # ----------------------------

        open_futures_risk = float(state.get("open_futures_risk", 0.0))
        open_fx_risk = float(state.get("open_fx_risk", 0.0))
        open_equities_risk = float(state.get("open_equities_risk", 0.0))
        open_crypto_risk = float(state.get("open_crypto_risk", 0.0))
        open_rates_risk = float(state.get("open_rates_risk", 0.0))

        # Add new trade risk to appropriate bucket
        fx_risk = open_fx_risk + trade_risk
        futures_risk = open_futures_risk
        equities_risk = open_equities_risk
        crypto_risk = open_crypto_risk
        rates_risk = open_rates_risk

        snap = self.portfolio_engine.snapshot(
            equity=equity,
            fx_risk=fx_risk,
            futures_risk=futures_risk,
            equities_risk=equities_risk,
            crypto_risk=crypto_risk,
            rates_risk=rates_risk,
        )

        if snap.allocation_pct > self.max_portfolio_risk_pct:
            return {
                "decision": "BLOCK",
                "policy": "live",
                "reasons": [
                    "PORTFOLIO_RISK_CAP_EXCEEDED",
                    f"allocation {snap.allocation_pct:.2%} > cap {self.max_portfolio_risk_pct:.2%}",
                ],
                "portfolio_allocation_pct": snap.allocation_pct,
                "portfolio_total_risk": snap.total_risk,
                "portfolio_components": snap.components,
            }

        # ----------------------------
        # APPROVED
        # ----------------------------

        return {
            "decision": "ALLOW",
            "policy": "live",
            "portfolio_allocation_pct": snap.allocation_pct,
        }
