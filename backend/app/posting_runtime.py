"""
Runtime Governance – Phase 18C
Capital Strata Systems (CSS)

Unified Runtime Enforcement:

Enforces:
- Valid ISO execution_date
- Active Financial Year boundary
- Month-end hard lock
- Year-end hard lock
- Backdated execution_date guard (execution_date < entry_date)
- Governed value_date enforcement (value_date < execution_date requires logged override)

All override decisions are logged immutably via PostingDateGovernor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from postings.api import PostingStore
from engine.posting.close_registry import CloseRegistry
from engine.fiscal.fiscal_calendar import FiscalCalendar

from .posting_date_policy import (
    PostingDateGovernor,
    PostingDatePolicy,
    DateOverrideRequest,
    DateOverrideDecision,
)

STORE = PostingStore()

# Execution-date override authority
EXECUTION_OVERRIDE_ROLES = {"ADMIN", "SUPER_USER"}


@dataclass(frozen=True)
class PostingOverride:
    approved_by_role: str
    reason: str


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

def _parse_iso_date(s: str, field_name: str) -> date:
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


# ---------------------------------------------------------
# Main Governance Gate
# ---------------------------------------------------------

def assert_open_for_posting(
    execution_date: str,
    value_date: str,
    actor_user_id: str,
    actor_role: str,
    override: Optional[dict] = None,
    entry_date: Optional[str] = None,
) -> None:
    """
    Runtime governance enforcement.

    Blocks:
    - execution_date outside active FY
    - YEAR_END closed
    - MONTH_END closed
    - execution_date < entry_date without override
    - value_date < execution_date without governed override (logged)
    """

    actor_role = str(actor_role).strip().upper()
    exec_date = _parse_iso_date(execution_date, "execution_date")
    val_date = _parse_iso_date(value_date, "value_date")
    ent_date = _parse_iso_date(entry_date, "entry_date") if entry_date else datetime.utcnow().date()

    ov = _normalize_override(override)

    # -----------------------------------------------------
    # 1) Financial Year boundary (non-bypassable)
    # -----------------------------------------------------
    active_fy = FiscalCalendar.get_active_fy()
    if not (active_fy.start_date <= exec_date <= active_fy.end_date):
        raise PermissionError(
            f"Posting blocked: execution_date {exec_date} outside active FY "
            f"{active_fy.fy_label} ({active_fy.start_date} → {active_fy.end_date})."
        )

    # -----------------------------------------------------
    # 2) Year-end lock
    # -----------------------------------------------------
    y = exec_date.year
    if CloseRegistry.is_closed("YEAR_END", y, None):
        raise PermissionError(f"Posting blocked: YEAR_END already closed for {y}.")

    # -----------------------------------------------------
    # 3) Month-end lock
    # -----------------------------------------------------
    m = exec_date.month
    if CloseRegistry.is_closed("MONTH_END", y, m):
        raise PermissionError(
            f"Posting blocked: MONTH_END already closed for {y:04d}-{m:02d}."
        )

    # -----------------------------------------------------
    # 4) Execution-date backdating guard
    # -----------------------------------------------------
    if exec_date < ent_date:
        if ov is None:
            raise PermissionError(
                f"Posting blocked: backdated execution_date {exec_date} < entry_date {ent_date}. "
                f"Requires override."
            )
        if ov.approved_by_role not in EXECUTION_OVERRIDE_ROLES:
            raise PermissionError(
                f"Posting blocked: override role '{ov.approved_by_role}' not authorized. "
                f"Requires one of: {sorted(EXECUTION_OVERRIDE_ROLES)}"
            )
        if len(ov.reason) < 10:
            raise PermissionError("Posting blocked: override reason required (min 10 chars).")

    # -----------------------------------------------------
    # 5) Value-date governance via PostingDateGovernor
    # -----------------------------------------------------
    governor = PostingDateGovernor(
        PostingDatePolicy()
    )

    if governor.requires_back_valuation_override(execution_date, value_date):

        if ov is None:
            raise PermissionError(
                f"Posting blocked: value_date {val_date} earlier than execution_date {exec_date}. "
                f"Governed override required."
            )

        # Create override request (logged later in decision)
        req: DateOverrideRequest = governor.create_back_valuation_override_request(
            requester_user_id=actor_user_id,
            txn_date=execution_date,
            value_date=value_date,
            reason=ov.reason,
            context={"source": "posting_runtime"},
        )

        decision: DateOverrideDecision = governor.decide_override(
            req=req,
            approver_user_id=actor_user_id,
            approver_band=actor_role,
            outcome="APPROVED",
            decision_reason=ov.reason,
        )

        if decision.outcome != "APPROVED":
            raise PermissionError(
                f"Posting blocked: value-date override not approved."
            )

    # If all checks pass → allowed to proceed