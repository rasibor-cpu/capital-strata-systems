"""
engine/reporting/business_calendar.py

Business Calendar & Previous Working Day Enforcement
----------------------------------------------------

Design:
- Weekends are non-business days (Sat/Sun)
- No holiday file yet (extendable later)
- Enforces:
    • No weekend signoff
    • No future date
    • Default policy: only previous working day allowed
    • Override-ready (future expansion)

This is Phase 18 – Temporal Governance Layer.
"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Tuple


# -------------------------------------------------
# Core Business Day Logic
# -------------------------------------------------

def is_business_day(d: date) -> bool:
    """
    Business days: Monday–Friday
    """
    return d.weekday() < 5  # 0=Mon, 6=Sun


def previous_business_day(reference: date | None = None) -> date:
    """
    Returns the most recent business day before 'reference'
    """
    reference = reference or datetime.now(timezone.utc).date()
    d = reference - timedelta(days=1)

    while not is_business_day(d):
        d -= timedelta(days=1)

    return d


# -------------------------------------------------
# Enforcement Layer
# -------------------------------------------------

def enforce_previous_day_policy(business_date: date) -> Tuple[bool, str]:
    """
    Enforces:
      - Not future
      - Must be business day
      - Must equal previous working day (strict policy)

    Returns:
      (approved: bool, reason: str)
    """

    today = datetime.now(timezone.utc).date()

    if business_date > today:
        return False, "Cannot sign off future date"

    if not is_business_day(business_date):
        return False, "Cannot sign off non-business day"

    expected = previous_business_day(today)

    if business_date != expected:
        return False, f"Signoff allowed only for previous working day ({expected.isoformat()})"

    return True, ""