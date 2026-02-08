"""
Execution Gate – Central Trade Approval Layer
REA Capital Trading Engine

Integrated with RiskGovernor
Fail-closed by design.

Phase 1:
- In-memory risk state by default
- Optional JSON persistence to disk (safe, best-effort)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

from engine.risk.risk_governor import RiskGovernor, apply_trade, apply_result


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionGate:
    """
    Central gate that:
    - Checks risk policy via RiskGovernor
    - Tracks trade counts and outcomes
    - Optionally persists state to JSON so it survives restarts
    """

    def __init__(self) -> None:
        self.risk_governor = RiskGovernor()

        # Optional: persist state to disk (default ON)
        self.persist_state = os.environ.get("REA_PERSIST_RISK_STATE", "1") == "1"
        self.state_path = os.environ.get(
            "REA_RISK_STATE_PATH",
            os.path.join("engine", "risk", "risk_state.json"),
        )

        # Default state (fail-closed expects these keys)
        self.state: Dict[str, Any] = {
            "day_key": "1970-01-01",
            "trades_today": 0,
            "open_positions": 0,
            "consecutive_losses": 0,
            "losses_by_pair": {},
            "cooldown_until": None,
            "last_update_utc": _utc_now_iso(),
        }

        # Best-effort load persisted state
        if self.persist_state:
            self._load_state_best_effort()

    # ------------------------------------------------------------
    # persistence (best-effort, never crash engine)
    # ------------------------------------------------------------

    def _load_state_best_effort(self) -> None:
        try:
            if not os.path.exists(self.state_path):
                return
            with open(self.state_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            # Merge (keep defaults if missing)
            if isinstance(loaded, dict):
                for k, v in loaded.items():
                    self.state[k] = v
                self.state["last_update_utc"] = _utc_now_iso()
        except Exception:
            # Fail-closed design: do NOT crash; just continue with in-memory state
            return

    def _save_state_best_effort(self) -> None:
        if not self.persist_state:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            self.state["last_update_utc"] = _utc_now_iso()
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, sort_keys=True)
        except Exception:
            return

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def evaluate_trade(
        self,
        *,
        instrument: str,
        equity_risk: float,
    ) -> Dict[str, Any]:
        """
        Evaluate whether a new trade is allowed under current policy + state.

        If approved, we increment trades_today immediately (apply_trade).
        (Execution can still be simulation-only depending on other gates.)
        """
        # Refresh policy + evaluate
        decision = self.risk_governor.evaluate(
            instrument=instrument,
            equity_risk=equity_risk,
            state=self.state,
        )

        if decision["decision"] == "BLOCK":
            self._save_state_best_effort()
            return {
                "status": "REJECTED",
                "risk_policy": decision["policy"],
                "reasons": decision["reasons"],
            }

        # Allowed → increment trade counter
        apply_trade(self.state)
        self._save_state_best_effort()

        return {
            "status": "APPROVED",
            "risk_policy": decision["policy"],
            "reasons": decision["reasons"],
        }

    def record_trade_result(
        self,
        *,
        instrument: str,
        pnl: float,
    ) -> Dict[str, Any]:
        """
        Record outcome of a completed trade (P&L) so the governor can enforce:
        - consecutive loss cap
        - losses per pair cap
        """
        apply_result(self.state, instrument=instrument, pnl=pnl)
        self._save_state_best_effort()

        return {
            "status": "RECORDED",
            "instrument": instrument,
            "pnl": pnl,
            "trades_today": self.state.get("trades_today"),
            "consecutive_losses": self.state.get("consecutive_losses"),
            "losses_by_pair": self.state.get("losses_by_pair", {}).get(instrument, 0),
            "cooldown_until": self.state.get("cooldown_until"),
        }

    def set_open_positions(self, *, open_positions: int) -> None:
        """
        Optional helper for later: let router/execution layer sync live open positions.
        """
        self.state["open_positions"] = int(open_positions)
        self._save_state_best_effort()
