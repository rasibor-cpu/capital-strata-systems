"""
backend/app/headless_guarded_entry.py

Phase 1 (Headless) guarded entrypoint for Capital Strata Systems / REA Capital Trading Engine.

Primary objectives:
- NO module-level imports from engine.risk.* to avoid circular imports.
- Fail-closed execution: SIMULATION allowed, PAPER/LIVE blocked unless explicitly unlocked.
- Stable callable surface for API: run_headless(req: dict, cfg: HeadlessConfig) -> dict

This file intentionally keeps imports minimal and defers engine imports until runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

@dataclass
class HeadlessConfig:
    """
    Headless engine configuration (Phase 1).

    execution_locked=True  -> SIMULATION only (fail-closed default)
    execution_locked=False -> PAPER/LIVE may be allowed by the engine policy checks (still guarded)
    """
    max_trades_per_day: int = 15
    max_consecutive_losses: int = 5
    cooldown_seconds: int = 3600
    max_positions: int = 20

    execution_locked: bool = True


# -------------------------------------------------------------------
# Engine runner (guarded)
# -------------------------------------------------------------------

def run_headless(*, req: Dict[str, Any], cfg: Optional[HeadlessConfig] = None) -> Dict[str, Any]:
    """
    Guarded headless run.

    Expected req fields (from API):
      steps (int), symbol (str), execution_mode (str),
      current_open_positions (int), trades_today (int), consecutive_losses (int),
      current_equity (float|int optional), peak_equity (float|int optional)

    Returns structured dict. Fail-closed on any exception.
    """
    ts = _utc_now_iso()
    cfg = cfg or HeadlessConfig()

    # -----------------------------
    # Validate request (fail-closed)
    # -----------------------------
    try:
        steps = int(req.get("steps", 5))
        symbol = str(req.get("symbol", "EURUSD"))
        execution_mode = str(req.get("execution_mode", "SIMULATION")).upper()

        current_open_positions = int(req.get("current_open_positions", 0))
        trades_today = int(req.get("trades_today", 0))
        consecutive_losses = int(req.get("consecutive_losses", 0))

        current_equity_raw = req.get("current_equity", None)
        peak_equity_raw = req.get("peak_equity", None)

        current_equity = float(current_equity_raw) if current_equity_raw is not None else 100000.0
        peak_equity = float(peak_equity_raw) if peak_equity_raw is not None else current_equity

        if steps < 1 or steps > 500:
            return {"ok": False, "timestamp_utc": ts, "error": "invalid_steps_range"}

        if not symbol:
            return {"ok": False, "timestamp_utc": ts, "error": "invalid_symbol"}

        if execution_mode not in {"SIMULATION", "PAPER", "LIVE"}:
            return {"ok": False, "timestamp_utc": ts, "error": "invalid_execution_mode"}

    except Exception as e:
        return {"ok": False, "timestamp_utc": ts, "error": f"bad_request: {type(e).__name__}: {e}"}

    # ----------------------------------------
    # Fail-closed execution mode enforcement
    # ----------------------------------------
    if cfg.execution_locked and execution_mode != "SIMULATION":
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": "execution_locked_fail_closed",
            "details": {"execution_mode": execution_mode, "execution_locked": True},
        }

    # ----------------------------------------------------------------
    # Import engine components LAZILY (prevents circular imports)
    # ----------------------------------------------------------------
    try:
        # NOTE: This import is intentionally inside the function.
        from engine.risk.risk_governor import RiskGovernor  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"engine_import_failed: {type(e).__name__}: {e}",
        }

    # ----------------------------------------
    # Initialize governor + seed runtime state
    # ----------------------------------------
    gov = RiskGovernor()

    try:
        # Keep governor state aligned with this run
        gov.update_equity(current_equity)
        # If your RiskGovernor tracks equity peak internally, update_equity already handles peak.
        # But we also try to set peak explicitly if the attribute exists.
        if hasattr(gov, "state") and isinstance(getattr(gov, "state"), dict):
            gov.state["equity_peak"] = max(float(gov.state.get("equity_peak", 0.0)), float(peak_equity))
            gov.state["trades_today"] = int(trades_today)
            gov.state["consecutive_losses"] = int(consecutive_losses)

    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"governor_state_seed_failed: {type(e).__name__}: {e}",
        }

    # ----------------------------------------
    # Run steps (SIMULATION by default)
    # ----------------------------------------
    decisions: List[Dict[str, Any]] = []
    approved = 0
    rejected = 0

    for i in range(steps):
        # Minimal deterministic “trade request” for Phase 1:
        # - stop distance fixed at 1%
        # - notional scales modestly; AdaptiveCapScaler inside RiskGovernor will clamp it
        notional = 1000.0 + (i * 100.0)
        stop_distance_pct = 0.01

        trade_req = {
            "instrument": symbol,
            "side": "buy",
            "notional": notional,
            "stop_distance_pct": stop_distance_pct,
            "policy": "core",
        }

        try:
            # Call governor directly (no external helper dependencies)
            # We build TradeRequest inside RiskGovernor via allow_trade().
            decision_obj = gov.allow_trade(  # type: ignore[attr-defined]
                type("TradeRequestProxy", (), trade_req)()  # lightweight proxy with attributes
            )

            # Normalize decision
            if hasattr(decision_obj, "as_dict"):
                dec = decision_obj.as_dict()
            elif hasattr(decision_obj, "__dict__"):
                dec = dict(decision_obj.__dict__)
            else:
                dec = {"ok": False, "reasons": ["unknown_decision_shape"]}

        except Exception:
            # Fallback: use apply_trade if allow_trade signature differs
            try:
                from engine.risk.risk_governor import apply_trade  # type: ignore
                dec = apply_trade(gov, trade_req)
            except Exception as e2:
                return {
                    "ok": False,
                    "timestamp_utc": _utc_now_iso(),
                    "error": f"risk_governor_call_failed: {type(e2).__name__}: {e2}",
                }

        decisions.append({"step": i + 1, "trade": trade_req, "decision": dec})

        if bool(dec.get("ok", False)):
            approved += 1
        else:
            rejected += 1

    return {
        "ok": True,
        "timestamp_utc": _utc_now_iso(),
        "execution_mode": execution_mode,
        "execution_locked": bool(cfg.execution_locked),
        "symbol": symbol,
        "steps": steps,
        "summary": {
            "approved": approved,
            "rejected": rejected,
            "current_open_positions": current_open_positions,
            "trades_today_in_request": trades_today,
            "consecutive_losses_in_request": consecutive_losses,
        },
        "decisions": decisions,
    }
