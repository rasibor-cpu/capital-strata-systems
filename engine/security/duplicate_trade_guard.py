"""
Duplicate Trade Guard – REA Capital Trading Engine (V1)

Goal:
- Detect "identical" trades and WARN (not block).
- Allow override (UI button later) to proceed anyway.
- Uses prior ledger history as truth source.

Definition of "duplicate" (practical V1):
- Same symbol, side, trade_type, currency, and amount
- Same execution_date (UTC date string)
- Entry/price similarity within tolerance if provided

Notes:
- We WARN by default; execution may proceed.
- Override is explicit: override_duplicate=True
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _safe_upper(x: Any) -> str:
    return str(x or "").upper().strip()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


@dataclass(frozen=True)
class DuplicateCheckResult:
    decision: str  # "OK" or "WARN"
    reason: str
    matches: int
    sample_match: Optional[Dict[str, Any]] = None


def _load_events(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def check_duplicate_trade(
    *,
    ledger_path: str,
    symbol: str,
    side: str,
    trade_type: str,
    currency: str,
    amount: float,
    execution_date: str,              # YYYY-MM-DD (UTC basis)
    entry_px: Optional[float] = None, # optional
    price_tol: float = 1e-6,
    lookback_days: int = 30,
    override_duplicate: bool = False,
) -> DuplicateCheckResult:
    """
    Returns WARN if a matching trade is found in lookback window, else OK.

    If override_duplicate=True, returns OK but includes reason and match count.
    """

    # If override requested, we still compute match count for audit, but decision is OK.
    sym = _safe_upper(symbol)
    sde = _safe_upper(side)
    ttp = _safe_upper(trade_type)
    ccy = _safe_upper(currency)
    amt = _safe_float(amount)

    # Load ledger events
    events = _load_events(ledger_path)

    now = datetime.now(timezone.utc)
    start_cut = now - timedelta(days=max(1, int(lookback_days)))

    matches: List[Dict[str, Any]] = []

    for e in events:
        try:
            ts = _parse_ts(str(e.get("ts_utc", "")))
        except Exception:
            continue

        if ts < start_cut:
            continue

        # Required fields in ledger (best-effort)
        e_sym = _safe_upper(e.get("symbol"))
        e_side = _safe_upper(e.get("side"))
        e_type = _safe_upper(e.get("trade_type"))
        e_ccy = _safe_upper(e.get("currency"))
        e_amt = _safe_float(e.get("amount"))

        e_exec_date = str(e.get("execution_date", ""))

        if (
            e_sym == sym
            and e_side == sde
            and e_type == ttp
            and e_ccy == ccy
            and abs(e_amt - amt) <= 1e-9
            and e_exec_date == execution_date
        ):
            # Optional price similarity check if both present
            if entry_px is not None and e.get("entry_px") is not None:
                e_entry = _safe_float(e.get("entry_px"))
                if abs(e_entry - float(entry_px)) > price_tol:
                    continue
            matches.append(e)

    if override_duplicate:
        return DuplicateCheckResult(
            decision="OK",
            reason=f"override_duplicate=True; {len(matches)} duplicate match(es) found" if matches else "override_duplicate=True; no duplicates found",
            matches=len(matches),
            sample_match=matches[0] if matches else None,
        )

    if matches:
        return DuplicateCheckResult(
            decision="WARN",
            reason=f"duplicate-like trade detected ({len(matches)} prior match(es) within lookback)",
            matches=len(matches),
            sample_match=matches[0],
        )

    return DuplicateCheckResult(decision="OK", reason="no duplicates found", matches=0)
