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
from typing import List


LOG_FILE = Path("execution_journal.log")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
) -> None:
    _write({
        "type": "decision",
        "timestamp_utc": _utc_now(),
        "instrument": instrument,
        "decision": decision,
        "policy": policy,
        "reasons": reasons,
        "equity": round(float(equity), 6),
        "equity_peak": round(float(equity_peak), 6),
        "mode": mode,
    })


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
        "equity": round(float(equity), 6),
        "equity_peak": round(float(equity_peak), 6),
    })
