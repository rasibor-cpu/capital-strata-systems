"""
Capital Strata Systems
Risk Governor – v3.4.1 Portfolio Governed

Institutional risk enforcement layer.

Enforces:
1. Rolling drawdown cap
2. Daily trade throttle
3. Cross-asset portfolio risk cap

Fail-closed by design.
"""

from __future__ import annotations

from typing import Dict, Any, List

from backend.app.execution_journal import record_trade_decision
from backend.app.risk.portfolio_risk_engine import PortfolioRiskEngine


class RiskGovernor:

    def __init__(self) -> None:

        # ----------------------------
        # Core Risk Controls
        # ----------------------------

        self.global_dd_limit = 0.05              # 5% rolling drawdown
        self.global_throttle_limit = 0.03        # 3% daily throttle
        self.max_portfolio_risk_pct = 0.08       # 8% total portfolio cap
        self.max_trades_per_day = 10

        # ----------------------------
        # Runtime State
        # ----------------------------

        self.trades_today = 0
        self.equity_peak = 0.0

        self.portfolio_engine = PortfolioRiskEngine()

        # Operational context
        self.policy = "live"
        self.mode = "live"

    # --------------------------------------------------------
    # Evaluate Trade
    # --------------------------------------------------------

    def evaluate(
        self,
        *,
        instrument: str,
        equity: float,
        trade_risk: float,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        equity = float(equity)
        trade_risk = float(trade_risk)

        if self.equity_peak <= 0:
            self.equity_peak = equity

        self.equity_peak = max(self.equity_peak, equity)

        reasons: List[str] = []

        # ----------------------------------------------------
        # 1. Rolling Drawdown
        # ----------------------------------------------------

        if self.equity_peak > 0:
            drawdown = (self.equity_peak - equity) / self.equity_peak
        else:
            drawdown = 0.0

        if drawdown >= self.global_dd_limit:
            decision = "BLOCK"
            reasons.append("GLOBAL_DRAWDOWN_LIMIT")

            self._log(
                instrument=instrument,
                decision=decision,
                reasons=reasons,
                equity=equity,
                state=state,
                trade_risk=trade_risk,
            )

            return {
                "decision": decision,
                "policy": self.policy,
                "reasons": reasons,
                "drawdown": round(drawdown, 6),
            }

        # ----------------------------------------------------
        # 2. Trade Throttle
        # ----------------------------------------------------

        if self.trades_today >= self.max_trades_per_day:
            decision = "BLOCK"
            reasons.append("TRADE_LIMIT_REACHED")

            self._log(
                instrument=instrument,
                decision=decision,
                reasons=reasons,
                equity=equity,
                state=state,
                trade_risk=trade_risk,
            )

            return {
                "decision": decision,
                "policy": self.policy,
                "reasons": reasons,
            }

        # ----------------------------------------------------
        # 3. Portfolio Exposure Enforcement
        # ----------------------------------------------------

        open_futures_risk = float(state.get("open_futures_risk", 0.0))

        snapshot = self.portfolio_engine.snapshot(
            equity=equity,
            fx_risk=trade_risk,
            futures_risk=open_futures_risk,
        )

        total_risk = snapshot.total_risk
        allocation_pct = snapshot.allocation_pct
        components = snapshot.components

        if allocation_pct > self.max_portfolio_risk_pct:

            decision = "BLOCK"
            reasons.append(
                f"PORTFOLIO_RISK_CAP_EXCEEDED: "
                f"{allocation_pct:.2%} > cap {self.max_portfolio_risk_pct:.2%}"
            )

            self._log(
                instrument=instrument,
                decision=decision,
                reasons=reasons,
                equity=equity,
                state=state,
                trade_risk=trade_risk,
                portfolio_total_risk=total_risk,
                portfolio_allocation_pct=allocation_pct,
                portfolio_components=components,
            )

            return {
                "decision": decision,
                "policy": self.policy,
                "reasons": reasons,
                "portfolio_allocation_pct": round(allocation_pct, 6),
                "portfolio_total_risk": round(total_risk, 6),
                "portfolio_components": components,
            }

        # ----------------------------------------------------
        # 4. APPROVED
        # ----------------------------------------------------

        decision = "ALLOW"

        self._log(
            instrument=instrument,
            decision=decision,
            reasons=["APPROVED"],
            equity=equity,
            state=state,
            trade_risk=trade_risk,
            portfolio_total_risk=total_risk,
            portfolio_allocation_pct=allocation_pct,
            portfolio_components=components,
        )

        return {
            "decision": decision,
            "policy": self.policy,
            "portfolio_allocation_pct": round(allocation_pct, 6),
        }

    # --------------------------------------------------------
    # Logging Wrapper
    # --------------------------------------------------------

    def _log(
        self,
        *,
        instrument: str,
        decision: str,
        reasons: List[str],
        equity: float,
        state: Dict[str, Any],
        trade_risk: float,
        portfolio_total_risk: float | None = None,
        portfolio_allocation_pct: float | None = None,
        portfolio_components: Dict[str, float] | None = None,
    ) -> None:

        record_trade_decision(
            instrument=instrument,
            decision=decision,
            policy=self.policy,
            reasons=reasons,
            equity=equity,
            equity_peak=self.equity_peak,
            mode=self.mode,
            portfolio_total_risk=portfolio_total_risk,
            portfolio_allocation_pct=portfolio_allocation_pct,
            portfolio_components=portfolio_components,
            max_portfolio_risk_pct=self.max_portfolio_risk_pct,
            equity_reference=equity,
        )
