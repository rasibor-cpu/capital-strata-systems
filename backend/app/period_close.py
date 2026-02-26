"""
period_close.py
---------------
Period Close & Locking Engine (GAAP / IFRS / Bank-Grade)

Purpose:
- Enforce month-end and year-end close
- Prevent postings into closed/locked periods
- Lock closed periods against mutation
- Route adjustments to next open period
- Preserve full audit trail

This is a CONTROL module. No postings occur here.

NOTE:
- This module is intentionally conservative.
- CLOSED/LOCKED periods are NOT overridable here.
  (Overrides for backdating/future dating within OPEN periods belong in posting_date_policy.py)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Any, Optional


# In-memory period registry (can later be persisted)
_PERIODS: Dict[str, Dict[str, Any]] = {}


# -----------------------------
# Period State Helpers
# -----------------------------

def _period_key(period_type: str, period_value: str) -> str:
    return f"{period_type}:{period_value}"


def get_period(period_type: str, period_value: str) -> Dict[str, Any]:
    key = _period_key(period_type, period_value)
    return _PERIODS.get(key, {
        "period_type": period_type,
        "period_value": period_value,
        "state": "OPEN",
        "closed_on": None,
        "closed_by": None,
        "locked": False,
    })


def set_period_state(
    period_type: str,
    period_value: str,
    state: str,
    user_id: str
) -> Dict[str, Any]:
    key = _period_key(period_type, period_value)

    _PERIODS[key] = {
        "period_type": period_type,
        "period_value": period_value,
        "state": state,
        "closed_on": datetime.utcnow().isoformat(),
        "closed_by": user_id,
        "locked": state in ("CLOSED", "LOCKED"),
    }
    return _PERIODS[key]


# -----------------------------
# Validation Gate
# -----------------------------

def _parse_iso_date(posting_date: str) -> Optional[date]:
    try:
        # Accept YYYY-MM-DD or full iso datetime; use date part.
        return datetime.fromisoformat(str(posting_date).replace("Z", "+00:00")).date()
    except Exception:
        return None


def is_posting_allowed(posting_date: str) -> bool:
    """
    Hard gate: determines if posting is allowed for a given date
    based on period close/lock states ONLY.
    """
    d = _parse_iso_date(posting_date)
    if d is None:
        return False

    month_key = d.strftime("%Y-%m")
    year_key = d.strftime("%Y")

    month = get_period("MONTH", month_key)
    year = get_period("YEAR", year_key)

    # Locked means NO postings, ever.
    if month["locked"] or year["locked"]:
        return False

    # Only OPEN periods accept postings.
    if month["state"] != "OPEN" or year["state"] != "OPEN":
        return False

    return True


# -----------------------------
# Close Operations
# -----------------------------

def close_month(year: int, month: int, user_id: str) -> Dict[str, Any]:
    """
    Close a financial month.
    """
    period_value = f"{year:04d}-{month:02d}"
    return set_period_state("MONTH", period_value, "CLOSED", user_id)


def close_year(year: int, user_id: str) -> Dict[str, Any]:
    """
    Close a financial year.
    """
    period_value = f"{year:04d}"
    return set_period_state("YEAR", period_value, "CLOSED", user_id)


def lock_year(year: int, user_id: str) -> Dict[str, Any]:
    """
    Irreversibly lock a financial year (audit lock).
    """
    period_value = f"{year:04d}"
    return set_period_state("YEAR", period_value, "LOCKED", user_id)


# -----------------------------
# Adjustment Routing
# -----------------------------

def next_open_period(posting_date: str) -> str:
    """
    Route adjustments to the next open period if original is closed/locked.
    Returns an ISO date (first day of next open month).
    """
    d = _parse_iso_date(posting_date)
    if d is None:
        # if invalid, route to today
        return date.today().isoformat()

    candidate = d

    while True:
        candidate = candidate.replace(day=1)
        month_key = candidate.strftime("%Y-%m")
        year_key = candidate.strftime("%Y")

        if (
            get_period("MONTH", month_key)["state"] == "OPEN" and
            get_period("YEAR", year_key)["state"] == "OPEN" and
            not get_period("MONTH", month_key)["locked"] and
            not get_period("YEAR", year_key)["locked"]
        ):
            return candidate.isoformat()

        # Move forward one month
        if candidate.month == 12:
            candidate = candidate.replace(year=candidate.year + 1, month=1)
        else:
            candidate = candidate.replace(month=candidate.month + 1)


# -----------------------------
# Reporting
# -----------------------------

def period_status() -> Dict[str, Any]:
    """
    Returns all period states for audit visibility.
    """
    return {
        "generated_on": date.today().isoformat(),
        "periods": list(_PERIODS.values()),
        "note": "Closed/Locked periods reject postings. Backdating controls live in posting_date_policy.py."
    }