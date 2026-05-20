"""
Canonical Phase 1 (Headless) guarded entrypoint for
Capital Strata Systems / REA Capital Trading Engine.

Fail-closed by design.

Primary responsibilities:
- Build execution context from request + environment
- Inject optional trade fields when present
- Apply explicit execution-mode fail-closed gating
- Compute capital caps and Phase 1 sizing
- Evaluate execution gate safely
- Never allow live execution unless explicitly enabled

Design notes:
- Imports are intentionally kept minimal.
- Engine imports are deferred until runtime where practical.
- max_positions is reserved for later enforcement phases.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class HeadlessConfig:
    # Fail-closed by default
    allow_paper: bool = False
    allow_live: bool = False

    # Sizing defaults (Phase 1)
    target_theoretical_notional_pct: float = 0.50  # produces 50k on 100k equity

    # Reserved for later enforcement
    max_positions: int = 1


def _env_float(name: str) -> Optional[float]:
    val = os.environ.get(name)
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


def _env_str(name: str) -> Optional[str]:
    val = os.environ.get(name)
    return val if val else None


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _as_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _as_str(v: Any, default: str) -> str:
    try:
        s = str(v).strip()
        return s if s else default
    except Exception:
        return default


def run_headless(req: Dict[str, Any], cfg: Optional[HeadlessConfig] = None) -> Dict[str, Any]:
    """
    Stable headless entry. Accepts:
      - run_headless(req)
      - run_headless(req, cfg)

    Returns JSON-serializable dict.
    """
    ts = utc_now_iso()
    cfg = cfg or HeadlessConfig()

    # -----------------------------
    # Parse request (safe defaults)
    # -----------------------------
    steps = _as_int(req.get("steps", 1), 1)
    symbol = _as_str(req.get("symbol", req.get("fx_instrument", "EUR_USD")), "EUR_USD")
    mode = _as_str(req.get("execution_mode", req.get("mode", "SIMULATION")), "SIMULATION").upper()

    current_open_positions = _as_int(req.get("current_open_positions", 0), 0)
    trades_today = _as_int(req.get("trades_today", 0), 0)
    consecutive_losses = _as_int(req.get("consecutive_losses", 0), 0)

    req_equity = req.get("current_equity")
    req_equity_peak = req.get("peak_equity")

    equity = (
        _as_float(req_equity, 0.0)
        if req_equity is not None
        else (_env_float("ACCOUNT_EQUITY") or 0.0)
    )
    equity_peak = (
        _as_float(req_equity_peak, equity)
        if req_equity_peak is not None
        else (_env_float("ACCOUNT_EQUITY_PEAK") or equity)
    )

    # -----------------------------
    # Fail-closed mode gating
    # -----------------------------
    if mode not in ("SIMULATION", "PAPER", "LIVE"):
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"invalid_execution_mode: {mode}",
        }

    if mode == "PAPER" and not cfg.allow_paper:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "mode": mode,
            "symbol": symbol,
            "error": "paper_blocked_fail_closed",
        }

    if mode == "LIVE" and not cfg.allow_live:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "mode": mode,
            "symbol": symbol,
            "error": "live_blocked_fail_closed",
        }

    # -----------------------------
    # Fail-closed validations
    # -----------------------------
    if steps <= 0 or steps > 10_000:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": "invalid_steps",
        }

    if equity <= 0:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "mode": mode,
            "symbol": symbol,
            "error": "invalid_current_equity_fail_closed",
        }

    if equity_peak <= 0:
        equity_peak = equity

    # -----------------------------
    # Lazy imports
    # -----------------------------
    try:
        from engine.capital.adaptive_cap_scaler import AdaptiveCapScaler  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"cap_scaler_import_error: {type(e).__name__}: {e}",
        }

    try:
        from engine.execution.execution_gate import ExecutionGate  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"execution_gate_import_error: {type(e).__name__}: {e}",
        }

    # -----------------------------
    # Compute caps
    # -----------------------------
    try:
        scaler = AdaptiveCapScaler()
        cap_dec = scaler.compute(
            equity=float(equity),
            equity_peak=float(equity_peak),
            regime="normal",
            cooldown_active=False,
        )
        caps = cap_dec.as_dict()
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"cap_scaler_compute_error: {type(e).__name__}: {e}",
        }

    # -----------------------------
    # Phase 1 sizing
    # -----------------------------
    risk_budget_abs = float(caps.get("risk_budget_pct", 0.0)) * float(equity)
    max_notional_abs = float(caps.get("max_position_notional_pct", 0.0)) * float(equity)

    theoretical_notional = float(cfg.target_theoretical_notional_pct) * float(equity)
    final_notional = min(theoretical_notional, max_notional_abs)

    sizing = {
        "ok": True,
        "risk_budget_abs": risk_budget_abs,
        "theoretical_notional": theoretical_notional,
        "max_notional_abs": max_notional_abs,
        "final_notional": final_notional,
        "capital_utilization_pct": (final_notional / float(equity)) if float(equity) else 0.0,
    }

    # -----------------------------
    # Execution gate evaluation
    # -----------------------------
    try:
        gate = ExecutionGate()
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"execution_gate_init_error: {type(e).__name__}: {e}",
        }

    try:
        gate.evaluate_trade(
            instrument=symbol,
            equity=float(equity),
            equity_peak=float(equity_peak),
        )
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"execution_gate_context_error: {type(e).__name__}: {e}",
        }

    side = _as_str(req.get("side", _env_str("TRADE_SIDE")), "")
    notional = (
        _as_float(req.get("notional"), 0.0)
        if req.get("notional") is not None
        else (_env_float("TRADE_NOTIONAL") or None)
    )
    stop_distance_pct = (
        _as_float(req.get("stop_distance_pct"), 0.0)
        if req.get("stop_distance_pct") is not None
        else (_env_float("TRADE_STOP_DISTANCE_PCT") or None)
    )

    try:
        gate_decision = gate.evaluate_trade(
            instrument=symbol,
            side=side or None,
            notional=notional,
            stop_distance_pct=stop_distance_pct,
            equity=float(equity),
            equity_peak=float(equity_peak),
        )
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"execution_gate_evaluate_error: {type(e).__name__}: {e}",
        }

    # -----------------------------
    # Return
    # -----------------------------
    return {
        "ok": True,
        "timestamp_utc": ts,
        "mode": mode,
        "symbol": symbol,
        "steps_executed": steps,
        "inputs": {
            "current_open_positions": current_open_positions,
            "trades_today": trades_today,
            "consecutive_losses": consecutive_losses,
            "current_equity": float(equity),
            "peak_equity": float(equity_peak),
        },
        "caps": caps,
        "sizing": sizing,
        "gate_decision": gate_decision,
    }