"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA Capital Trading Engine

Fail-closed by design.

Phase 1 additions:
- Optional persistence for risk state (REA_PERSIST_RISK_STATE=1)

IMPORTANT:
- No module-level imports from engine.risk.* to avoid circular imports.
  RiskGovernor + TradeRequest are lazy-imported inside __init__.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


from engine.risk.risk_state_store import load_state, save_state


class ExecutionGate:
    """
    Thin orchestration layer around RiskGovernor.

    This gate:
    - loads persisted state (if enabled)
    - hydrates RiskGovernor.state
    - evaluates trades via RiskGovernor.allow_trade()
    - updates open_positions locally (Phase 1 simplified)
    - records realized outcomes via RiskGovernor.record_trade_outcome()
    """

    def __init__(self) -> None:
        # Lazy import to avoid circular imports
        from engine.risk.risk_governor import RiskGovernor  # type: ignore

        self.risk_governor = RiskGovernor()

        # Load persisted state (or defaults) and bind it to governor.state
        persisted = load_state()
        if isinstance(persisted, dict) and persisted:
            # Merge into governor.state (governor remains source-of-truth)
            self.risk_governor.state.update(persisted)

        # We keep a reference for convenience
        self.state: Dict[str, Any] = self.risk_governor.state

        # Phase 1 field that may not exist in governor defaults
        if "open_positions" not in self.state:
            self.state["open_positions"] = 0

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
        }

    def sync_context(
        self,
        *,
        day_key: Optional[str] = None,
        equity: Optional[float] = None,
        equity_peak: Optional[float] = None,
        cooldown_active: Optional[bool] = None,
        regime: Optional[str] = None,
        open_positions: Optional[int] = None,
    ) -> None:
        """
        Optional helper to sync state from API/headless request context.
        Safe: only updates when a value is provided.
        """
        if day_key is not None:
            self.risk_governor.set_day(str(day_key))

        if equity is not None:
            self.risk_governor.update_equity(float(equity))

        if equity_peak is not None:
            # governor updates peak automatically in update_equity, but allow explicit override
            self.state["equity_peak"] = float(equity_peak)

        if cooldown_active is not None:
            self.risk_governor.set_cooldown(bool(cooldown_active))

        if regime is not None:
            self.risk_governor.set_regime(str(regime))

        if open_positions is not None:
            self.state["open_positions"] = int(open_positions)

        self._persist()

    def evaluate_trade(
        self,
        *,
        instrument: str,
        side: str,
        notional: float,
        stop_distance_pct: float,
        policy: str = "core",
    ) -> Dict[str, Any]:
        """
        Evaluate whether a proposed trade is allowed.

        NOTE:
        - RiskGovernor decides via allow_trade(TradeRequest)
        - ExecutionGate maintains open_positions (Phase 1 simplified)
        """
        # Lazy import to match current RiskGovernor API
        from engine.risk.risk_governor import TradeRequest  # type: ignore

        req = TradeRequest(
            instrument=str(instrument),
            side=str(side),
            notional=float(notional),
            stop_distance_pct=float(stop_distance_pct),
            policy=str(policy),
        )

        dec = self.risk_governor.allow_trade(req).as_dict()

        if not dec.get("ok", False):
            out = {
                "status": "REJECTED",
                "decision": dec,
                "snapshot": self.snapshot(instrument),
            }
            self._persist()
            return out

        # Allowed → increment open_positions (Phase 1 simplified)
        self.state["open_positions"] = int(self.state.get("open_positions") or 0) + 1

        out = {
            "status": "APPROVED",
            "decision": dec,
            "open_positions": self.state["open_positions"],
            "snapshot": self.snapshot(instrument),
        }
        self._persist()
        return out

    def record_trade_result(
        self,
        *,
        instrument: str,
        pnl: float,
    ) -> Dict[str, Any]:
        """
        Record realized PnL and update loss streak logic.

        Assumption (Phase 1):
        - each recorded result closes 1 open position (if any are open)
        - realized pnl updates daily_pnl and consecutive_losses via RiskGovernor
        """
        # Close one position if any are open
        if int(self.state.get("open_positions") or 0) > 0:
            self.state["open_positions"] = int(self.state.get("open_positions") or 0) - 1

        self.risk_governor.record_trade_outcome(float(pnl))
        self._persist()

        snap = self.snapshot(instrument)
        snap["pnl"] = float(pnl)

        return {
            "status": "RECORDED",
            "snapshot": snap,
        }
