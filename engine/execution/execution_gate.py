"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA Capital Trading Engine

Fail-closed by design.

Phase 1 additions:
- Optional persistence for risk state (REA_PERSIST_RISK_STATE=1)

IMPORTANT:
- No module-level imports from engine.risk.* to avoid circular imports.
  RiskGovernor + TradeRequest are lazy-imported inside __init__ / evaluate_trade.
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

    Compatibility:
    - Some callers may "probe" the gate with partial context (instrument only).
      In that case, we return a structured fail-closed rejection instead of raising.
    """

    def __init__(self) -> None:
        from engine.risk.risk_governor import RiskGovernor  # type: ignore

        self.risk_governor = RiskGovernor()

        # Compatibility: ensure we have a dict-like state container
        gov_state = getattr(self.risk_governor, "state", None)
        if not isinstance(gov_state, dict):
            gov_state = {}
            try:
                setattr(self.risk_governor, "state", gov_state)
            except Exception:
                pass

        self.state: Dict[str, Any] = gov_state

        # Load persisted state (or defaults)
        persisted = load_state()
        if isinstance(persisted, dict) and persisted:
            self.state.update(persisted)

        # Ensure governor.state points to same dict
        try:
            setattr(self.risk_governor, "state", self.state)
        except Exception:
            pass

        # Defaults (safe)
        self.state.setdefault("open_positions", 0)
        self.state.setdefault("day_key", None)
        self.state.setdefault("equity", None)
        self.state.setdefault("equity_peak", None)
        self.state.setdefault("trades_today", 0)
        self.state.setdefault("daily_pnl", 0.0)
        self.state.setdefault("consecutive_losses", 0)
        self.state.setdefault("cooldown_active", False)
        self.state.setdefault("regime", None)
        self.state.setdefault("last_extras", None)

        self._persist()

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
        if day_key is not None:
            try:
                self.risk_governor.set_day(str(day_key))
            except Exception:
                self.state["day_key"] = str(day_key)

        if equity is not None:
            try:
                self.risk_governor.update_equity(float(equity))
            except Exception:
                self.state["equity"] = float(equity)

        if equity_peak is not None:
            self.state["equity_peak"] = float(equity_peak)

        if cooldown_active is not None:
            try:
                self.risk_governor.set_cooldown(bool(cooldown_active))
            except Exception:
                self.state["cooldown_active"] = bool(cooldown_active)

        if regime is not None:
            try:
                self.risk_governor.set_regime(str(regime))
            except Exception:
                self.state["regime"] = str(regime)

        if open_positions is not None:
            self.state["open_positions"] = int(open_positions)

        self._persist()

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
        Evaluate whether a proposed trade is allowed.

        Full mode:
          requires side, notional, stop_distance_pct

        Probe mode (compatibility):
          if any required fields missing, return a structured fail-closed rejection.
        """
        # Record extras (e.g., equity_risk) for diagnostics
        self.state["last_extras"] = {k: extras[k] for k in sorted(extras.keys())} if extras else None

        missing = []
        if side is None:
            missing.append("side")
        if notional is None:
            missing.append("notional")
        if stop_distance_pct is None:
            missing.append("stop_distance_pct")

        if missing:
            # Fail-closed, structured response (no exception)
            out = {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "missing_required_fields",
                    "missing": missing,
                    "note": "Caller must provide side/notional/stop_distance_pct for full evaluation.",
                },
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # Full evaluation path
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
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        self.state["open_positions"] = int(self.state.get("open_positions") or 0) + 1

        out = {
            "status": "APPROVED",
            "decision": dec,
            "open_positions": self.state["open_positions"],
            "snapshot": self.snapshot(str(instrument)),
        }
        self._persist()
        return out

    def record_trade_result(
        self,
        *,
        instrument: str,
        pnl: float,
    ) -> Dict[str, Any]:
        if int(self.state.get("open_positions") or 0) > 0:
            self.state["open_positions"] = int(self.state.get("open_positions") or 0) - 1

        try:
            self.risk_governor.record_trade_outcome(float(pnl))
        except Exception:
            self.state["daily_pnl"] = float(self.state.get("daily_pnl") or 0.0) + float(pnl)
            if float(pnl) < 0:
                self.state["consecutive_losses"] = int(self.state.get("consecutive_losses") or 0) + 1
            else:
                self.state["consecutive_losses"] = 0

        self._persist()

        snap = self.snapshot(str(instrument))
        snap["pnl"] = float(pnl)

        return {
            "status": "RECORDED",
            "snapshot": snap,
        }
