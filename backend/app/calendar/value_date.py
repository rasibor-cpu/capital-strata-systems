"""
backend/app/calendar/value_date.py

Single choke-point for value-date / settlement-date computation.

Rules:
- Skip weekends and any registered holidays (global + branch scoped).
- Default behavior is conservative (fail-safe): if anything errors, return trade_date.

Typical defaults (can be tuned later):
- FX: T+2
- Equities: T+2
- Options: T+1 (placeholder)
- Crypto: T+0
"""

from __future__ import annotations

from datetime import date

try:
    # This module is expected to exist after your holiday work:
    # backend/app/calendar/holiday_calendar.py
    from backend.app.calendar.holiday_calendar import shift_value_date
except Exception:  # fail-safe
    shift_value_date = None  # type: ignore


def default_settlement_days(asset_class: str) -> int:
    ac = (asset_class or "").strip().lower()
    if ac in ("crypto",):
        return 0
    if ac in ("fx", "forex"):
        return 2
    if ac in ("equity", "equities", "stock", "stocks"):
        return 2
    if ac in ("options",):
        return 1
    # fallback
    return 0


def compute_value_date(
    trade_date: date,
    asset_class: str,
    branch: str | None = None,
    settlement_days: int | None = None,
) -> date:
    """
    Compute business value date with holiday/weekend skipping.

    settlement_days:
      - if None -> uses default_settlement_days(asset_class)
      - else -> explicit business-day shift
    """
    days = default_settlement_days(asset_class) if settlement_days is None else int(settlement_days)

    # fail-safe: if holiday shifter not available, no shift beyond raw calendar add
    if shift_value_date is None:
        # Minimal safe behavior: return trade_date for 0; else still business shift not possible -> raw trade_date.
        return trade_date if days == 0 else trade_date

    try:
        # shift_value_date shifts BUSINESS days and also rolls forward if start is non-business day (days==0).
        return shift_value_date(start=trade_date, business_days=days, branch=branch, direction="forward")
    except Exception:
        return trade_date
