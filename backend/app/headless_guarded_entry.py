"""
Phase 1 (Headless) guarded entrypoint for
Capital Strata Systems / REA Capital Trading Engine.

Primary objectives:
- NO module-level imports from engine.* to avoid circular imports.
- Fail-closed execution: SIMULATION allowed; PAPER/LIVE blocked unless explicitly unlocked.
- Stable callable surface for API:
    run_headless(req: dict, cfg: HeadlessConfig) -> dict

This file intentionally keeps imports minimal and defers optional engine imports until runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _upper(v: Any, default: str = "") -> str:
    try:
        return str(v).strip().upper()
    except Exception:
        return default


@dataclass
class HeadlessConfig:
    # Risk / guard defaults (Phase 1)
    max_trades_per_day: int = 15
    max_positions: int = 20
    max_consecutive_losses: int = 5
    cooldown_seconds: int = 3600

    # Fail-closed execution controls
    execution_locked: bool = True  # if True, PAPER/LIVE are blocked
    allow_paper: bool = False
    allow_live: bool = False

    # Basic equity drawdown guard (pct)
    max_drawdown_pct: float = 0.25  # 25%

    def as_dict(self) -> Dict[str, Any]:
        return {
            "max_trades_per_day": self.max_trades_per_day,
            "max_positions": self.max_positions,
            "max_consecutive_losses": self.max_consecutive_losses,
            "cooldown_seconds": self.cooldown_seconds,
            "execution_locked": self.execution_locked,
            "allow_paper": self.allow_paper,
            "allow_live": self.allow_live,
            "max_drawdown_pct": self.max_drawdown_pct,
        }


def _guard_concurrency(open_positions: int, max_positions: int) -> Dict[str, Any]:
    ok = open_positions < max_positions
    return {
        "ok": ok,
        "name": "concurrency_guard",
        "open_positions": open_positions,
        "max_positions": max_positions,
        "reason": None if ok else "max_positions_reached",
    }


def _guard_daily_trades(trades_today: int, max_trades_per_day: int) -> Dict[str, Any]:
    ok = trades_today < max_trades_per_day
    return {
        "ok": ok,
        "name": "daily_trade_guard",
        "trades_today": trades_today,
        "max_trades_per_day": max_trades_per_day,
        "reason": None if ok else "max_trades_per_day_reached",
    }


def _guard_loss_streak(consecutive_losses: int, max_consecutive_losses: int) -> Dict[str, Any]:
    ok = consecutive_losses < max_consecutive_losses
    return {
        "ok": ok,
        "name": "loss_streak_guard",
        "consecutive_losses": consecutive_losses,
        "max_consecutive_losses": max_consecutive_losses,
        "reason": None if ok else "max_consecutive_losses_reached",
    }


def _guard_drawdown(current_equity: float, peak_equity: float, max_drawdown_pct: float) -> Dict[str, Any]:
    peak = max(peak_equity, 1e-9)
    dd = max(0.0, (peak - max(current_equity, 0.0)) / peak)
    ok = dd <= max_drawdown_pct
    return {
        "ok": ok,
        "name": "equity_drawdown_guard",
        "current_equity": current_equity,
        "peak_equity": peak_equity,
        "drawdown_pct": dd,
        "max_drawdown_pct": max_drawdown_pct,
        "reason": None if ok else "max_drawdown_reached",
    }


def _compute_caps_best_effort(
    *,
    equity: float,
    equity_peak: float,
    cooldown_active: bool,
    regime: str,
) -> Dict[str, Any]:
    """
    Best-effort cap snapshot.
    If engine.capital.adaptive_cap_scaler exists, we use it.
    Otherwise we return conservative defaults.
    """
    # Conservative defaults (fail-closed)
    caps: Dict[str, Any] = {
        "source": "fallback",
        "risk_budget_pct": 0.0025,            # 0.25% per-trade-ish budget baseline
        "max_position_notional_pct": 0.10,    # 10% notional cap baseline
        "reasons": ["fallback_caps_used"],
        "inputs": {
            "equity": equity,
            "equity_peak": equity_peak,
            "cooldown_active": cooldown_active,
            "regime": regime,
        },
    }

    try:
        # Lazy import to avoid circular imports
        from engine.capital.adaptive_cap_scaler import AdaptiveCapScaler  # type: ignore

        scaler = AdaptiveCapScaler()
        cap_dec = scaler.compute(
            equity=float(equity),
            equity_peak=float(equity_peak),
            regime=str(regime),
            cooldown_active=bool(cooldown_active),
        )
        # Normalize
        if hasattr(cap_dec, "as_dict"):
            caps = cap_dec.as_dict()  # type: ignore
            caps["source"] = "AdaptiveCapScaler.as_dict"
        elif hasattr(cap_dec, "__dict__"):
            caps = dict(cap_dec.__dict__)  # type: ignore
            caps["source"] = "AdaptiveCapScaler.__dict__"
        else:
            caps = {"source": "AdaptiveCapScaler", "raw": str(cap_dec)}
        return caps
    except Exception as e:
        caps["source"] = "fallback"
        caps["caps_error"] = f"{type(e).__name__}: {e}"
        return caps


def run_headless(req: Dict[str, Any], cfg: HeadlessConfig) -> Dict[str, Any]:
    """
    Stable headless entrypoint.

    Expected req keys (best-effort):
      steps, symbol, execution_mode,
      current_open_positions, trades_today, consecutive_losses,
      current_equity, peak_equity,
      cooldown_active, regime

    Returns:
      ok, timestamp_utc, mode, symbol, steps_executed,
      guards, caps, trace
    """
    ts = _utc_now_iso()

    try:
        steps = _to_int(req.get("steps", 5), 5)
        steps = max(1, min(steps, 500))

        symbol = str(req.get("symbol", "EURUSD")).strip() or "EURUSD"
        mode = _upper(req.get("execution_mode", "SIMULATION"), "SIMULATION")

        current_open_positions = _to_int(req.get("current_open_positions", 0), 0)
        trades_today = _to_int(req.get("trades_today", 0), 0)
        consecutive_losses = _to_int(req.get("consecutive_losses", 0), 0)

        current_equity = _to_float(req.get("current_equity", 0.0), 0.0)
        peak_equity = _to_float(req.get("peak_equity", current_equity), current_equity)

        cooldown_active = bool(req.get("cooldown_active", False))
        regime = str(req.get("regime", "normal")).strip() or "normal"

    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"bad_request_parse: {type(e).__name__}: {e}",
        }

    # ------------------------------------------------------------
    # Fail-closed execution mode gate
    # ------------------------------------------------------------
    if mode in {"LIVE", "PAPER"}:
        if cfg.execution_locked:
            return {
                "ok": False,
                "timestamp_utc": ts,
                "mode": mode,
                "symbol": symbol,
                "error": f"execution_locked_fail_closed: {mode} blocked",
                "cfg": cfg.as_dict(),
            }
        if mode == "PAPER" and not cfg.allow_paper:
            return {
                "ok": False,
                "timestamp_utc": ts,
                "mode": mode,
                "symbol": symbol,
                "error": "paper_not_allowed_fail_closed",
                "cfg": cfg.as_dict(),
            }
        if mode == "LIVE" and not cfg.allow_live:
            return {
                "ok": False,
                "timestamp_utc": ts,
                "mode": mode,
                "symbol": symbol,
                "error": "live_not_allowed_fail_closed",
                "cfg": cfg.as_dict(),
            }

    if mode not in {"SIMULATION", "PAPER", "LIVE"}:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "mode": mode,
            "symbol": symbol,
            "error": "invalid_execution_mode",
        }

    # ------------------------------------------------------------
    # Guards (self-contained; no engine.risk imports)
    # ------------------------------------------------------------
    guards: List[Dict[str, Any]] = []
    guards.append(_guard_concurrency(current_open_positions, cfg.max_positions))
    guards.append(_guard_daily_trades(trades_today, cfg.max_trades_per_day))
    guards.append(_guard_loss_streak(consecutive_losses, cfg.max_consecutive_losses))
    guards.append(_guard_drawdown(current_equity, peak_equity, cfg.max_drawdown_pct))

    all_ok = all(bool(g.get("ok")) for g in guards)

    # ------------------------------------------------------------
    # Caps snapshot (best-effort)
    # ------------------------------------------------------------
    caps = _compute_caps_best_effort(
        equity=float(current_equity),
        equity_peak=float(peak_equity),
        cooldown_active=bool(cooldown_active),
        regime=str(regime),
    )

    # ------------------------------------------------------------
    # Trace (Phase 1: deterministic “no-trade” simulation trace)
    # We keep this safe: it proves loop execution + shows state/guards.
    # ------------------------------------------------------------
    trace: List[Dict[str, Any]] = []
    step_count = 0

    for i in range(steps):
        step_count += 1
        trace.append(
            {
                "step": i + 1,
                "action": "noop",
                "mode": mode,
                "symbol": symbol,
                "guards_ok": all_ok,
                "guards": guards,
                "caps": caps,
            }
        )

    # If guards fail, we still return trace but mark ok=False (fail-closed)
    if not all_ok:
        reasons = [g.get("reason") for g in guards if not g.get("ok") and g.get("reason")]
        return {
            "ok": False,
            "timestamp_utc": ts,
            "mode": mode,
            "symbol": symbol,
            "steps_executed": step_count,
            "error": "guard_block_fail_closed",
            "reasons": reasons,
            "guards": guards,
            "caps": caps,
        }

    # Success response (expanded)
    return {
        "ok": True,
        "timestamp_utc": ts,
        "mode": mode,
        "symbol": symbol,
        "steps_executed": step_count,
        "guards": guards,
        "caps": caps,
        "trace": trace,
    }
