"""
Execution Gate – Central Trade Approval Layer
REA Capital Trading Engine

Integrated with RiskGovernor
Fail-closed by design.

Phase 1 additions:
- Optional persistence for risk state (REA_PERSIST_RISK_STATE=1)
"""

from __future__ import annotations

from typing import Dict, Any

from engine.risk.risk_governor import RiskGovernor, apply_trade, apply_result
from engine.risk.risk_state_store import load_state, save_state


class ExecutionGate:

    def __init__(self):
        self.risk_governor = RiskGovernor()

        # Phase 1: state may be persisted (or defaulted) via state store
        self.state = load_state()

    def snapshot(self, instrument: str) -> Dict[str, Any]:
        # safe shallow snapshot for prints / audit
        return {
            "instrument": instrument,
            "day_key": self.state.get("day_key"),
            "trades_today": self.state.get("trades_today"),
            "open_positions": self.state.get("open_positions"),
            "consecutive_losses": self.state.get("consecutive_losses"),
            "losses_by_pair": self.state.get("losses_by_pair", {}).get(instrument, 0),
            "cooldown_until": self.state.get("cooldown_until"),
            "daily_pnl": self.state.get("daily_pnl", 0.0),
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
            out = {
                "status": "REJECTED",
                "risk_policy": decision["policy"],
                "reasons": decision["reasons"],
                "snapshot": self.snapshot(instrument),
            }
            save_state(self.state)
            return out

        # Allowed → increment trade counter + open position (Phase 1 simplified)
        apply_trade(self.state)
        self.state["open_positions"] = int(self.state.get("open_positions") or 0) + 1

        out = {
            "status": "APPROVED",
            "risk_policy": decision["policy"],
            "reasons": decision["reasons"],
            "open_positions": self.state["open_positions"],
            "snapshot": self.snapshot(instrument),
        }

        save_state(self.state)
        return out

    def record_trade_result(
        self,
        *,
        instrument: str,
        pnl: float,
    ) -> Dict[str, Any]:
        """
        Record realized PnL and update loss counters.
        Assumption (Phase 1): each recorded result closes 1 open position.
        """

        # Close one position if any are open
        if int(self.state.get("open_positions") or 0) > 0:
            self.state["open_positions"] -= 1

        apply_result(self.state, instrument=instrument, pnl=pnl)
        save_state(self.state)

        snap = self.snapshot(instrument)
        snap["pnl"] = pnl

        return {
            "status": "RECORDED",
            "snapshot": snap,
        }
