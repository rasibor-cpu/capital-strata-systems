"""
engine/reporting/report_printer.py
Capital Strata Systems (CSS)

Phase 23D.6 — Report Printer Date Hardening

Fix:
- Accept str / date / datetime
- Normalize safely
- Never call isoformat() on a string
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Any, Dict


# ---------------------------------------------------------
# DATE NORMALIZATION (critical fix)
# ---------------------------------------------------------

def _normalize_to_date(val: Any) -> date:
    """
    Accepts str | date | datetime.
    Always returns date.
    """
    if isinstance(val, date) and not isinstance(val, datetime):
        return val

    if isinstance(val, datetime):
        return val.date()

    if isinstance(val, str):
        return datetime.strptime(val, "%Y-%m-%d").date()

    raise TypeError(f"Unsupported date type: {type(val)}")


# ---------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------

def run_eod_pack(
    run_date: Optional[Any] = None,
    as_of_date: Optional[Any] = None,
    ledger_date: Optional[Any] = None,
    date: Optional[Any] = None,
) -> Dict[str, Any]:

    raw_date = run_date or as_of_date or ledger_date or date
    if raw_date is None:
        raw_date = datetime.utcnow().date()

    report_date = _normalize_to_date(raw_date)

    print(f"EOD Report Pack Date: {report_date.isoformat()}")

    # ---------------------------------------------------------
    # PLACEHOLDER: Insert real report generation logic here
    # ---------------------------------------------------------

    # This stub ensures stable return contract
    return {
        "ok": True,
        "fn": "run_eod_pack",
        "report_date": report_date.isoformat(),
    }


# Backward compatibility aliases
generate_eod_pack = run_eod_pack
print_eod_pack = run_eod_pack
run_daily_pack = run_eod_pack