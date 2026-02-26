"""
Runtime singletons for Posting workflow – Phase 18B
Capital Strata Systems

Enforces:
- Active Financial Year boundary
- Month-end hard lock
- Year-end hard lock
"""

from __future__ import annotations

from datetime import datetime, date
from postings.api import PostingStore

from engine.posting.close_registry import CloseRegistry
from engine.fiscal.fiscal_calendar import FiscalCalendar


# Shared in-memory ticket store
STORE = PostingStore()


def _parse_execution_date(execution_date: str) -> date:
    """
    Expect ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM...
    """
    try:
        return datetime.fromisoformat(execution_date).date()
    except Exception:
        raise ValueError("Invalid execution_date format. Use ISO format.")


def assert_open_for_posting(execution_date: str, actor_role: str) -> None:
    """
    Governance enforcement:

    1) Execution date must fall inside ACTIVE financial year.
    2) Posting blocked if month is closed.
    3) Posting blocked if year-end already closed.
    """

    exec_date = _parse_execution_date(execution_date)

    # -----------------------------------
    # 1) Financial Year Boundary Check
    # -----------------------------------
    active_fy = FiscalCalendar.get_active_fy()

    if not (active_fy.start_date <= exec_date <= active_fy.end_date):
        raise PermissionError(
            f"Posting blocked: execution_date {exec_date} outside active FY "
            f"{active_fy.fy_label} "
            f"({active_fy.start_date} → {active_fy.end_date})."
        )

    # -----------------------------------
    # 2) Year-End Hard Lock
    # -----------------------------------
    year = exec_date.year
    if CloseRegistry.is_closed("YEAR_END", year, None):
        raise PermissionError(
            f"Posting blocked: YEAR_END already closed for {year}."
        )

    # -----------------------------------
    # 3) Month-End Hard Lock
    # -----------------------------------
    month = exec_date.month
    if CloseRegistry.is_closed("MONTH_END", year, month):
        raise PermissionError(
            f"Posting blocked: MONTH_END already closed for "
            f"{year:04d}-{month:02d}."
        )