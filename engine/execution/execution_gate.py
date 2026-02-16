"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA Capital

Fail-closed by design.

Key design rules:
- Accepts extra diagnostic / capital inputs safely
- Validates only required trade fields
- Ignores non-trade parameters (probe / guarded mode)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from engine.risk.risk_state_store import load_state, save_state


class ExecutionGate:
    """
    Thin orchestration layer around RiskGovernor.

    Responsibilities:
    - Load persisted risk state
    - Hydrate RiskGovernor.state
    - Evaluate trade permission
    - Track open positions (Phase 1)
    """

    def __init__(self) -> None:
        from engine.risk.risk_governor import RiskGovernor  # lazy import

        self.risk_governor = RiskGovernor()

        persisted = load_state()
        if isinstance(persisted, dict) and persisted:
            self.risk_governor.state.update(persisted)

        self.state: Dict[str, Any] = self.risk_governor.state

        if "open_positions" not in self.state:
            self.state["open_positions"] = 0

    # ------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------

    def _persist(self) -> None:
        save_state(self.state)

    def snapshot(self, instrument: str) -> Dict[str, Any]:
        return {
            "instrument": instrument,
            "day_key": self.state.get("day_key"),
            "equity": self.state.get("equity"),
            "equity_peak": self.state.get("equity_peak"),
            "trades_today": self.state.get("trades_today"),
            "daily_pnl": self.state.get("daily_pnl"),
            "consecutive_losses": self.state.get("consecutive_losses"),
            "cooldown_active": self.state.get("cooldown_active"),
            "regime": self.state.get("regime"),
            "open_positions": self.state.get("open_positions"),
            "last_extras": self.state.get("last_extras"),
        }

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def evaluate_trade(
        self,
        *,
        instrument: str,
        side: Optional[str] = None,
        notional: Optional[float] = None,
        stop_distance_pct: Optional[float] = None,
        policy: str = "core",
        **extras: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate whether a trade is allowed.

        NOTES:
        - extras absorbs diagnostic / capital inputs (equity_risk, volatility, etc.)
        - missing trade fields => clean rejection (probe-safe)
        """

        # Store extras for diagnostics / audit
        if extras:
            self.state["last_extras"] = extras

        # Required trade fields check
        missing = []
        if side is None:
            missing.append("side")
        if notional is None:
            missing.append("notional")
        if stop_distance_pct is None:
            missing.append("stop_distance_pct")

        if missing:
            out = {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "missing_required_fields",
                    "missing": missing,
                    "note": "Caller must provide side/notional/stop_distance_pct for full evaluation",
                },
                "snapshot": self.snapshot(instrument),
            }
            self._persist()
            return out

        # Lazy import to avoid circulars
        from engine.risk.risk_governor import TradeRequest

        req = TradeRequest(
            instrument=str(instrument),
            side=str(side),
            notional=float(notional),
            stop_distance_pct=float(stop_distance_pct),
            policy=str(policy),
        )

        decision = self.risk_governor.allow_trade(req).as_dict()

        if not decision.get("ok", False):
            out = {
                "status": "REJECTED",
                "decision": decision,
                "snapshot": self.snapshot(instrument),
            }
            self._persist()
            return out

        # Phase 1: increment open positions
        self.state["open_positions"] = int(self.state.get("open_positions") or 0) + 1

        out = {
            "status": "APPROVED",
            "decision": decision,
            "open_positions": self.state["open_positions"],
            "snapshot": self.snapshot(instrument),
        }

        self._persist()
        return out

    def record_trade_result(self, *, instrument: str, pnl: float) -> Dict[str, Any]:
        if int(self.state.get("open_positions") or 0) > 0:
            self.state["open_positions"] -= 1

        self.risk_governor.record_trade_outcome(float(pnl))
        self._persist()

        snap = self.snapshot(instrument)
        snap["pnl"] = float(pnl)

        return {
            "status": "RECORDED",
            "snapshot": snap,
        }
