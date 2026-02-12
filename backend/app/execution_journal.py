"""
Capital Strata Systems
Execution Journal – Audit & Governance Log

Centralized execution + shutdown logging.
Append-only. No deletions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


LOG_FILE = Path("execution_journal.log")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return round(float(x), 6)
    except Exception:
        return None


def _clean_components(d: Any) -> Dict[str, float] | None:
    if d is None:
        return None
    if not isinstance(d, dict):
        return None
    out: Dict[str, float] = {}
    for k, Pure in d.items():
        try:
            out[str(k)] = round(float(Pure), 6)
        except Exception:
            # skip bad values
            continue
    return out


def _write(entry: dict) -> None:
    line = json.dumps(entry, separators=(",", ":"))
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ----------------------------------------------------------
# Trade Decision Logging
# ----------------------------------------------------------

def record_trade_decision(
    *,
    instrument: str,
    decision: str,
    policy: str,
    reasons: List[str],
    equity: float,
    equity_peak: float,
    mode: str,
    # --- Optional Portfolio Telemetry (backward-compatible) ---
    portfolio_total_risk: float | None = None,
    portfolio_allocation_pct: float | None = None,
    portfolio_components: Dict[str, float] | None = None,
    max_portfolio_risk_pct: float | None = None,
    equity_reference: float | None = None,
) -> None:
    entry: Dict[str, Any] = {
        "type": "decision",
        "timestamp_utc": _utc_now(),
        "instrument": instrument,
        "decision": decision,
        "policy": policy,
        "reasons": reasons,
        "equity": _clean_float(equity),
        "equity_peak": _clean_float(equity_peak),
        "mode": mode,
    }

    # Only include telemetry keys if present (keeps logs tidy)
    ptr = _clean_float(portfolio_total_risk)
    pap = _clean_float(portfolio_allocation_pct)
    mpp = _clean_float(max_portfolio_risk_pct)
    eref = _clean_float(equity_reference)
    comps = _clean_components(portfolio_components)

    if ptr is not None:
        entry["portfolio_total_risk"] = ptr
    if pap is not None:
        entry["portfolio_allocation_pct"] = pap
    if comps is not None:
        entry["portfolio_components"] = comps
    if mpp is not None:
        entry["max_portfolio_risk_pct"] = mpp
    if eref is not None:
        entry["equity_reference"] = eref

    _write(entry)


# ----------------------------------------------------------
# Order Result Logging
# ----------------------------------------------------------

def record_order_result(
    *,
    instrument: str,
    ok: bool,
    status: int | None,
    error: str | None,
    trade_id: str | None,
    mode: str,
) -> None:
    _write({
        "type": "order_result",
        "timestamp_utc": _utc_now(),
        "instrument": instrument,
        "ok": ok,
        "status": status,
        "error": error,
        "trade_id": trade_id,
        "mode": mode,
    })


# ----------------------------------------------------------
# Global Shutdown Logging
# ----------------------------------------------------------

def record_global_shutdown(
    reason: str,
    equity: float,
    equity_peak: float,
) -> None:
    _write({
        "type": "global_shutdown",
        "timestamp_utc": _utc_now(),
        "reason": reason,
        "equity": _clean_float(equity),
        "equity_peak": _clean_float(equity_peak),
    })
