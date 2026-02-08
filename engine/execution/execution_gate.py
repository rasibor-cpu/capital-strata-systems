"""
Execution Gate – Central Trade Approval Layer
REA Capital Trading Engine

Integrated with RiskGovernor
Fail-closed by design.

Phase-1:
- In-memory state
- Micro mode compatible
- Tracks open positions correctly
- Records trade results
- Passes equity into RiskGovernor (required for daily drawdown kill-switch)

Equity sourcing (Phase-1 safe):
- Preferred: caller passes equity=...
- Fallback: REA_DEFAULT_EQUITY env var (float) if caller does not pass equity
- Fail-closed if no equity available
"""

from __future__ import annotations

import os
from typing import Dict, Any, Optional

from engine.risk.risk_governor import RiskGovernor, apply_trade, apply_result


class ExecutionGate:
    def __init__(self):
        self.risk_governor = RiskGovernor()

        # Phase-1 in-memory state
        self.state: Dict[str, Any] = {
            "day_key": "1970-01-01",
            "trades_today": 0,
            "open_positions": 0,
            "consecutive_losses": 0,
            "losses_by_pair": {},
            "cooldown_until": None,
            "daily_pnl": 0.0,
        }

    # ============================================================
    # Helpers
    # ============================================================

    def _get_equity(self, equity: Optional[float]) -> Optional[float]:
        """
        Phase-1 safe equity retrieval.

        Preferred: explicit equity passed by caller (broker adapter will do this).
        Fallback: REA_DEFAULT_EQUITY env var for local testing.

        Returns:
            float equity or None if not available.
        """
        if equity is not None:
            try:
                eq = float(equity)
                return eq if eq > 0 else None
            except Exception:
                return None

        env_val = os.environ.get("REA_DEFAULT_EQUITY", "").strip()
        if env_val:
            try:
                eq = float(env_val)
                return eq if eq > 0 else None
            except Exception:
                return None

        return None

    def _risk_snapshot(self, instrument: str) -> Dict[str, Any]:
        return {
            "instrument": instrument,
            "day_key": self.state.get("day_key"),
            "trades_today": int(self.state.get("trades_today", 0)),
            "open_positions": int(self.state.get("open_positions", 0)),
            "consecutive_losses": int(self.state.get("consecutive_losses", 0)),
            "losses_by_pair": int(self.state.get("losses_by_pair", {}).get(instrument, 0)),
            "cooldown_until": self.state.get("cooldown_until"),
            "daily_pnl": float(self.state.get("daily_pnl", 0.0)),
        }

    # ============================================================
    # Trade Evaluation
    # ============================================================

    def evaluate_trade(
        self,
        *,
        instrument: str,
        equity_risk: float,
        equity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate whether a trade is allowed under current risk policy.

        equity:
            Should be supplied by broker layer (OANDA/Alpaca) as account equity.
            In Phase-1 local tests, you can set REA_DEFAULT_EQUITY.
        """

        eq = self._get_equity(equity)

        if eq is None:
            # Fail-closed: we cannot enforce daily drawdown without equity
            snap = self._risk_snapshot(instrument)
            return {
                "status": "REJECTED",
                "risk_policy": "UNKNOWN",
                "reasons": ["Missing equity (pass equity=... or set REA_DEFAULT_EQUITY)"],
                "snapshot": snap,
            }

        decision = self.risk_governor.evaluate(
            instrument=instrument,
            equity_risk=equity_risk,
            equity=eq,
            state=self.state,
        )

        if decision["decision"] == "BLOCK":
            snap = self._risk_snapshot(instrument)
            return {
                "status": "REJECTED",
                "risk_policy": decision["policy"],
                "reasons": decision["reasons"],
                "snapshot": snap,
            }

        # Approved → increment counters
        apply_trade(self.state)

        snap = self._risk_snapshot(instrument)
        return {
            "status": "APPROVED",
            "risk_policy": decision["policy"],
            "reasons": decision["reasons"],
            "snapshot": snap,
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
        """
        Record a realized PnL for a closed trade (or simulated result).
        """
        apply_result(self.state, instrument, pnl)

        snap = self._risk_snapshot(instrument)
        snap["pnl"] = float(pnl)

        return {
            "status": "RECORDED",
            "snapshot": snap,
        }
