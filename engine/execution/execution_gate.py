"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA Capital Trading Engine

Fail-closed by design.

Compatibility goals:
- tolerate RiskGovernor implementations that DO NOT expose:
  - .state
  - TradeRequest dataclass
  - strict allow_trade(TradeRequest) signatures
- tolerate upstream callers that "probe" the gate without full trade fields

This file is deliberately defensive and audit-friendly.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from engine.risk.risk_state_store import load_state, save_state


class ExecutionGate:
    """
    Thin orchestration layer around RiskGovernor.

    Responsibilities:
    - load/merge persisted state into a dict-like governor state container
    - provide evaluate_trade() API for headless + runners
    - keep a Phase-1 simplified open_positions counter
    """

    def __init__(self) -> None:
        # Lazy import to avoid circular imports
        from engine.risk.risk_governor import RiskGovernor  # type: ignore

        self.risk_governor = RiskGovernor()

        # Ensure dict-like state exists (some governors don't expose it)
        gov_state = getattr(self.risk_governor, "state", None)
        if not isinstance(gov_state, dict):
            gov_state = {}
            try:
                setattr(self.risk_governor, "state", gov_state)
            except Exception:
                pass

        self.state: Dict[str, Any] = gov_state

        # Merge persisted state
        persisted = load_state()
        if isinstance(persisted, dict) and persisted:
            self.state.update(persisted)

        # Keep governor.state aligned to our dict
        try:
            setattr(self.risk_governor, "state", self.state)
        except Exception:
            pass

        # Safe defaults
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

        Probe mode:
          if missing required fields → fail-closed structured rejection (no crash)

        RiskGovernor API compatibility:
          - if TradeRequest exists, use it
          - else pass a dict payload to allow_trade()
        """
        self.state["last_extras"] = {k: extras[k] for k in sorted(extras.keys())} if extras else None

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
                    "note": "Caller must provide side/notional/stop_distance_pct for full evaluation.",
                },
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # Build a normalized request payload
        req_payload: Dict[str, Any] = {
            "instrument": str(instrument),
            "side": str(side),
            "notional": float(notional),
            "stop_distance_pct": float(stop_distance_pct),
            "policy": str(policy),
        }

        # 1) Try TradeRequest if present
        req_obj: Any = req_payload
        try:
            from engine.risk.risk_governor import TradeRequest  # type: ignore

            req_obj = TradeRequest(**req_payload)  # type: ignore[arg-type]
        except Exception:
            # TradeRequest not available → we fall back to dict payload
            req_obj = req_payload

        # 2) Call allow_trade defensively
        try:
            allow_fn = getattr(self.risk_governor, "allow_trade", None)
            if allow_fn is None:
                raise AttributeError("RiskGovernor has no allow_trade()")

            result = allow_fn(req_obj)

            # Normalize decision into dict
            if isinstance(result, dict):
                dec = result
            else:
                # Many governors return an object with .as_dict()
                as_dict = getattr(result, "as_dict", None)
                dec = as_dict() if callable(as_dict) else {"ok": bool(result), "raw": str(result)}

        except Exception as e:
            out = {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "allow_trade_exception",
                    "error": str(e),
                },
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # Fail-closed if decision does not explicitly ok=True
        if not dec.get("ok", False):
            out = {
                "status": "REJECTED",
                "decision": dec,
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # Approved → increment open_positions
        self.state["open_positions"] = int(self.state.get("open_positions") or 0) + 1

        out = {
            "status": "APPROVED",
            "decision": dec,
            "open_positions": self.state["open_positions"],
            "snapshot": self.snapshot(str(instrument)),
        }
        self._persist()
        return out

    def record_trade_result(self, *, instrument: str, pnl: float) -> Dict[str, Any]:
        if int(self.state.get("open_positions") or 0) > 0:
            self.state["open_positions"] = int(self.state.get("open_positions") or 0) - 1

        try:
            fn = getattr(self.risk_governor, "record_trade_outcome", None)
            if callable(fn):
                fn(float(pnl))
            else:
                raise AttributeError("RiskGovernor has no record_trade_outcome()")
        except Exception:
            # Basic fallback accounting
            self.state["daily_pnl"] = float(self.state.get("daily_pnl") or 0.0) + float(pnl)
            if float(pnl) < 0:
                self.state["consecutive_losses"] = int(self.state.get("consecutive_losses") or 0) + 1
            else:
                self.state["consecutive_losses"] = 0

        self._persist()

        snap = self.snapshot(str(instrument))
        snap["pnl"] = float(pnl)
        return {"status": "RECORDED", "snapshot": snap}
