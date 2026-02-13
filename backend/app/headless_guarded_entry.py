"""
Phase 1 (Headless) guarded entrypoint for
Capital Strata Systems / REA Capital Trading Engine.

Includes:
- Lazy RiskGovernor loading
- Adaptive cap scaling
- Trade sizing layer
- Fail-closed logic
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------
# Headless Config
# ------------------------------------------------------------

@dataclass
class HeadlessConfig:
    allow_live: bool = False
    allow_paper: bool = False


# ------------------------------------------------------------
# Trade Sizing Engine
# ------------------------------------------------------------

def compute_position_size(
    equity: float,
    risk_budget_pct: float,
    max_notional_pct: float,
    stop_distance_pct: float,
) -> Dict[str, Any]:
    """
    Risk-based position sizing.

    risk_budget_abs = equity * risk_budget_pct
    position_size = risk_budget_abs / stop_distance_pct

    Then enforce max_notional_pct cap.
    """

    if equity <= 0:
        return {"ok": False, "error": "invalid_equity"}

    if stop_distance_pct <= 0 or stop_distance_pct >= 0.25:
        return {"ok": False, "error": "invalid_stop_distance"}

    risk_budget_abs = equity * risk_budget_pct
    theoretical_notional = risk_budget_abs / stop_distance_pct

    max_notional_abs = equity * max_notional_pct

    final_notional = min(theoretical_notional, max_notional_abs)

    capital_utilization_pct = final_notional / equity

    return {
        "ok": True,
        "risk_budget_abs": risk_budget_abs,
        "theoretical_notional": theoretical_notional,
        "max_notional_abs": max_notional_abs,
        "final_notional": final_notional,
        "capital_utilization_pct": capital_utilization_pct,
    }


# ------------------------------------------------------------
# Headless Entrypoint
# ------------------------------------------------------------

def run_headless(req: Dict[str, Any], cfg: Optional[HeadlessConfig] = None) -> Dict[str, Any]:

    ts = _utc_now_iso()

    if cfg is None:
        cfg = HeadlessConfig()

    try:
        # Lazy import to avoid circular dependency
        from engine.risk.risk_governor import RiskGovernor

        governor = RiskGovernor()

        equity = float(req.get("current_equity", 100000))
        peak_equity = float(req.get("peak_equity", equity))

        governor.update_equity(equity)

        # Pull caps via dummy trade request (lightweight call)
        from engine.capital.adaptive_cap_scaler import AdaptiveCapScaler

        scaler = AdaptiveCapScaler()
        cap_dec = scaler.compute(
            equity=equity,
            equity_peak=peak_equity,
            regime="normal",
            cooldown_active=False,
        )

        caps = cap_dec.as_dict()

        sizing = compute_position_size(
            equity=equity,
            risk_budget_pct=caps["risk_budget_pct"],
            max_notional_pct=caps["max_position_notional_pct"],
            stop_distance_pct=0.01,  # 1% stop assumption for now
        )

        if not sizing["ok"]:
            return {
                "ok": False,
                "timestamp_utc": ts,
                "error": sizing["error"],
            }

        return {
            "ok": True,
            "timestamp_utc": ts,
            "mode": req.get("execution_mode", "SIMULATION"),
            "symbol": req.get("symbol"),
            "steps_executed": req.get("steps", 0),
            "caps": caps,
            "sizing": sizing,
        }

    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": ts,
            "error": f"{type(e).__name__}: {e}",
        }
