"""
Execution Gate – Central Trade Approval Layer
REA Capital Trading Engine

Integrated with RiskGovernor
Fail-closed by design.
"""

from __future__ import annotations

from typing import Dict, Any

from engine.risk.risk_governor import RiskGovernor, apply_trade


class ExecutionGate:

    def __init__(self):
        self.risk_governor = RiskGovernor()

        # In-memory state (Phase 1)
        self.state = {
            "day_key": "1970-01-01",
            "trades_today": 0,
            "open_positions": 0,
            "consecutive_losses": 0,
            "losses_by_pair": {},
            "cooldown_until": None,
        }

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

        # If allowed → increment trade counter
        apply_trade(self.state)

        return {
            "status": "APPROVED",
            "risk_policy": decision["policy"],
            "reasons": decision["reasons"],
        }
