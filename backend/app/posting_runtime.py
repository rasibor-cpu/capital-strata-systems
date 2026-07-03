"""
Runtime singletons for Posting workflow – Phase 18B+
Capital Strata Systems

Enforces:
- Valid ISO execution_date (reject invalid calendar dates)
- Active Financial Year boundary
- Month-end hard lock
- Year-end hard lock
- Back-valued (backdated) posting blocked unless authorized override is provided

Back-valued definition:
- execution_date < entry_date (defaults to today UTC)
- entry_date can be supplied explicitly for testing or for cheque workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Optional

from postings.api import PostingStore
from engine.posting.close_registry import CloseRegistry
from engine.fiscal.fiscal_calendar import FiscalCalendar


STORE = PostingStore()

OVERRIDE_ROLES = {"ADMIN", "SUPER_USER"}


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass(frozen=True)
class PostingOverride:
    approved_by_role: str
    reason: str


def _parse_iso_date(s: str, field_name: str) -> date:
    """
    Accepts:
      - YYYY-MM-DD
      - YYYY-MM-DDTHH:MM:SS
    Rejects invalid calendar dates (e.g., 2026-02-30) with a clear message.
    """
    try:
        return datetime.fromisoformat(s).date()
    except ValueError as e:
        raise ValueError(f"Invalid {field_name}: {e}")
    except Exception:
        raise ValueError(f"Invalid {field_name}. Use ISO format like 2027-05-01.")


def _normalize_override(override: Optional[dict]) -> Optional[PostingOverride]:
    if override is None:
        return None
    role = str(override.get("approved_by_role", "")).strip().upper()
    reason = str(override.get("reason", "")).strip()
    return PostingOverride(approved_by_role=role, reason=reason)


def assert_open_for_posting(
    execution_date: str,
    actor_role: str,
    override: Optional[dict] = None,
    entry_date: Optional[str] = None,
) -> None:
    """
    Governance enforcement:

    1) execution_date must be valid ISO date
    2) execution_date must be inside ACTIVE FY window
    3) block if YEAR_END closed for execution_date.year
    4) block if MONTH_END closed for execution_date.year-month
    5) block back-valued (execution_date < entry_date) unless override authorized

    override format:
      {
        "approved_by_role": "SUPER_USER",
        "reason": "Back-valued cheque approved due to settlement alignment",
      }
    """

    actor_role = str(actor_role).strip().upper()

    exec_date = _parse_iso_date(execution_date, "execution_date")
    ent_date = _parse_iso_date(entry_date, "entry_date") if entry_date else _utc_today()

    ov = _normalize_override(override)

    # -----------------------------------
    # 1) Financial Year boundary (non-bypassable)
    # -----------------------------------
    active_fy = FiscalCalendar.get_active_fy()
    if not (active_fy.start_date <= exec_date <= active_fy.end_date):
        raise PermissionError(
            f"Posting blocked: execution_date {exec_date} outside active FY "
            f"{active_fy.fy_label} ({active_fy.start_date} → {active_fy.end_date})."
        )

    # -----------------------------------
    # 2) Year-end lock
    # -----------------------------------
    y = exec_date.year
    if CloseRegistry.is_closed("YEAR_END", y, None):
        raise PermissionError(f"Posting blocked: YEAR_END already closed for {y}.")

    # -----------------------------------
    # 3) Month-end lock
    # -----------------------------------
    m = exec_date.month
    if CloseRegistry.is_closed("MONTH_END", y, m):
        raise PermissionError(f"Posting blocked: MONTH_END already closed for {y:04d}-{m:02d}.")

    # -----------------------------------
    # 4) Back-valued (backdated) cheque guard
    # -----------------------------------
    if exec_date < ent_date:
        if ov is None:
            raise PermissionError(
                f"Posting blocked: back-valued execution_date {exec_date} < entry_date {ent_date}. "
                f"Requires override."
            )
        if ov.approved_by_role not in OVERRIDE_ROLES:
            raise PermissionError(
                f"Posting blocked: override role '{ov.approved_by_role}' not authorized. "
                f"Requires one of: {sorted(OVERRIDE_ROLES)}"
            )
        if len(ov.reason) < 10:
            raise PermissionError("Posting blocked: override reason required (min 10 chars).")
