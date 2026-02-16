"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA Capital

Fail-closed by design.

This version is GOVERNOR-AGNOSTIC:
- Does NOT assume RiskGovernor exposes .state
- Maintains its own persisted state dict (open_positions, last_extras, etc.)
- Attempts to hydrate RiskGovernor only if supported
- Probe-safe: missing trade fields => clean rejection (no crash)
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import inspect

from engine.risk.risk_state_store import load_state, save_state


class ExecutionGate:
    """
    Thin orchestration layer around RiskGovernor.

    Responsibilities:
    - Load persisted state (ExecutionGate-owned)
    - Attempt to hydrate RiskGovernor (if supported)
    - Evaluate trades via RiskGovernor.allow_trade()
    - Track open positions (Phase 1 simplified)
    """

    def __init__(self) -> None:
        # Lazy import to avoid circular imports
        from engine.risk.risk_governor import RiskGovernor  # type: ignore

        self.risk_governor = RiskGovernor()

        # ----------------------------
        # ExecutionGate-owned state
        # ----------------------------
        persisted = load_state()
        if isinstance(persisted, dict):
            self.state: Dict[str, Any] = dict(persisted)
        else:
            self.state = {}

        # Defaults
        self.state.setdefault("open_positions", 0)
        self.state.setdefault("last_extras", None)

        # Best-effort: hydrate governor if it supports any known mechanism
        self._try_hydrate_governor(self.state)

        # Persist immediately so brand-new machines get a clean baseline file
        self._persist()

    # ------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------

    def _persist(self) -> None:
        save_state(self.state)

    def _try_hydrate_governor(self, state: Dict[str, Any]) -> None:
        """
        Best-effort governor hydration.

        We try a few common patterns WITHOUT assuming any one exists:
        - governor.state (dict)  [older builds]
        - governor.hydrate(state_dict)
        - governor.load_state(state_dict)
        - governor.set_state(state_dict)
        """
        rg = self.risk_governor

        try:
            if hasattr(rg, "state") and isinstance(getattr(rg, "state"), dict):
                getattr(rg, "state").update(state)  # type: ignore[attr-defined]
                return
        except Exception:
            pass

        for meth_name in ("hydrate", "load_state", "set_state"):
            try:
                meth = getattr(rg, meth_name, None)
                if callable(meth):
                    meth(state)  # type: ignore[misc]
                    return
            except Exception:
                # ignore — fail-closed behavior is enforced at decision time
                pass

    def snapshot(self, instrument: str) -> Dict[str, Any]:
        # Keep snapshot stable even if state is minimal
        return {
            "instrument": instrument,
            "day_key": self.state.get("day_key"),
            "equity": self.state.get("equity"),
            "equity_peak": self.state.get("equity_peak"),
            "trades_today": self.state.get("trades_today"),
            "daily_pnl": self.state.get("daily_pnl", 0.0),
            "consecutive_losses": self.state.get("consecutive_losses", 0),
            "cooldown_active": self.state.get("cooldown_active", False),
            "regime": self.state.get("regime"),
            "open_positions": self.state.get("open_positions", 0),
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

        Probe-safe:
        - If required fields are missing, we REJECT with a clear payload.
        Governor-agnostic:
        - We attempt to build a TradeRequest if available; else pass dict into allow_trade().
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

        # Build request payload (works for both object-based and dict-based governors)
        req_dict = {
            "instrument": str(instrument),
            "side": str(side),
            "notional": float(notional),
            "stop_distance_pct": float(stop_distance_pct),
            "policy": str(policy),
        }

        # Try to use TradeRequest if it exists in this build; otherwise, pass dict.
        req_obj: Any = req_dict
        try:
            from engine.risk.risk_governor import TradeRequest  # type: ignore

            req_obj = TradeRequest(
                instrument=req_dict["instrument"],
                side=req_dict["side"],
                notional=req_dict["notional"],
                stop_distance_pct=req_dict["stop_distance_pct"],
                policy=req_dict["policy"],
            )
        except Exception:
            # No TradeRequest in this build; dict fallback is intentional
            req_obj = req_dict

        # Call governor.allow_trade (fail-closed)
        try:
            allow_trade = getattr(self.risk_governor, "allow_trade")
            if not callable(allow_trade):
                raise AttributeError("RiskGovernor.allow_trade is not callable")

            # Some governors might accept kwargs instead of a single req object
            sig = None
            try:
                sig = inspect.signature(allow_trade)
            except Exception:
                sig = None

            if sig and len(sig.parameters) >= 2:
                # Prefer passing a single req object/dict
                decision = allow_trade(req_obj)  # type: ignore[misc]
            else:
                # Extremely defensive fallback
                decision = allow_trade(req_obj)  # type: ignore[misc]

        except Exception as e:
            out = {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "allow_trade_exception",
                    "error": str(e),
                },
                "snapshot": self.snapshot(instrument),
            }
            self._persist()
            return out

        # Normalize decision to dict
        try:
            if hasattr(decision, "as_dict") and callable(getattr(decision, "as_dict")):
                dec = decision.as_dict()
            elif isinstance(decision, dict):
                dec = decision
            else:
                # best-effort stringify
                dec = {"ok": False, "reason": "unrecognized_decision_format", "raw": str(decision)}
        except Exception as e:
            dec = {"ok": False, "reason": "decision_normalization_exception", "error": str(e)}

        if not dec.get("ok", False):
            out = {
                "status": "REJECTED",
                "decision": dec,
                "snapshot": self.snapshot(instrument),
            }
            self._persist()
            return out

        # Allowed → increment open_positions (Phase 1)
        self.state["open_positions"] = int(self.state.get("open_positions") or 0) + 1

        out = {
            "status": "APPROVED",
            "decision": dec,
            "open_positions": self.state["open_positions"],
            "snapshot": self.snapshot(instrument),
        }
        self._persist()
        return out

    def record_trade_result(self, *, instrument: str, pnl: float) -> Dict[str, Any]:
        """
        Record realized PnL.

        Phase 1 assumption:
        - each recorded result closes 1 open position (if any are open)

        If governor exposes record_trade_outcome(), we call it.
        """
        if int(self.state.get("open_positions") or 0) > 0:
            self.state["open_positions"] = int(self.state.get("open_positions") or 0) - 1

        try:
            rto = getattr(self.risk_governor, "record_trade_outcome", None)
            if callable(rto):
                rto(float(pnl))  # type: ignore[misc]
        except Exception:
            # fail-closed mindset: we still persist local state
            pass

        self._persist()

        snap = self.snapshot(instrument)
        snap["pnl"] = float(pnl)

        return {"status": "RECORDED", "snapshot": snap}
