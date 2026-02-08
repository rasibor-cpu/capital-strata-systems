"""
Execution Gate – Central Trade Approval Layer
REA Capital Trading Engine

Integrated with RiskGovernor
Fail-closed by design.

Phase-1:
- In-memory state
- Micro mode compatible
- Tracks open positions correctly
"""

from __future__ import annotations

from typing import Dict, Any

from engine.risk.risk_governor import (
    RiskGovernor,
    apply_trade,
    apply_result,
)


class ExecutionGate:

    def __init__(self):
        self.risk_governor = RiskGovernor()

        # Phase-1 in-memory state
        self.state = {
            "day_key": "1970-01-01",
            "trades_today": 0,
            "open_positions": 0,
            "consecutive_losses": 0,
            "losses_by_pair": {},
            "cooldown_until": None,
        }

    # ============================================================
    # Trade Evaluation
    # ============================================================

    def evaluate_trade(
        self,
        *,
        instrument: str,
        equity_risk: float,
    ) -> Dict[str, Any]:

        decision = self.risk_governor.evaluate(
            instrument=instrument,
            equity_risk=equity_risk,
            state=self.state,
        )

        if decision["decision"] == "BLOCK":
            return {
                "status": "REJECTED",
                "risk_policy": decision["policy"],
                "reasons": decision["reasons"],
            }

        # Approved → increment counters
        apply_trade(self.state)
        self.state["open_positions"] += 1

        return {
            "status": "APPROVED",
            "risk_policy": decision["policy"],
            "reasons": decision["reasons"],
            "open_positions": self.state["open_positions"],
        }

    # ============================================================
    # Trade Result Recording
    # ============================================================

    def record_trade_result(
        self,
        *,
        instrument: str,
        pnl: float,
    ) -> Dict[str, Any]:

        # Decrement open positions safely
        if self.state["open_positions"] > 0:
            self.state["open_positions"] -= 1
        else:
            self.state["open_positions"] = 0  # fail-safe floor

        apply_result(self.state, instrument, pnl)

        return {
            "status": "RECORDED",
            "instrument": instrument,
            "pnl": pnl,
            "trades_today": self.state["trades_today"],
            "open_positions": self.state["open_positions"],
            "consecutive_losses": self.state["consecutive_losses"],
            "losses_by_pair": self.state["losses_by_pair"].get(instrument, 0),
            "cooldown_until": self.state.get("cooldown_until"),
        }
