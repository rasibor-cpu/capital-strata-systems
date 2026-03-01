"""
backend/app/posting_calendar.py

Posting Calendar Governance Engine – Phase 24A
----------------------------------------------

Purpose:
- Enforce posting execution-date and value-date rules (fail-closed).
- Prevent posting into closed financial periods.
- Prevent posting before system go-live date.
- Require overrides for backdating (execution or value date).

Design notes:
- This module does NOT decide whether a user is authorized to override.
  That belongs to the governance / approval layer (posting_approval.py).
- This module enforces that an override is present when required, and
  produces a structured decision to be logged into audit trails.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Dict, Any, List


# -----------------------------
# Data Models
# -----------------------------

@dataclass(frozen=True)
class CalendarOverride:
    """
    Override payload included with a posting request.
    Authorization is checked elsewhere; this module only enforces presence/shape.
    """
    override_type: str          # e.g., "BACKDATE_EXECUTION_DATE", "BACKDATE_VALUE_DATE", "CLOSED_PERIOD_POST"
    override_reason: str        # free text, required
    override_by_user_id: str    # who is claiming the override
    override_ticket_ref: str    # unique reference for traceability (can be approval code / ticket / memo ref)


@dataclass(frozen=True)
class CalendarDecision:
    status: str                 # "ALLOW" | "BLOCK" | "OVERRIDE_REQUIRED"
    reason_code: str            # stable machine-readable code
    message: str                # human-readable explanation
    required_override_type: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class PostingCalendarPolicy:
    """
    Policy is expected to be loaded at startup / session initialization (per your governance rule).
    """
    system_go_live_date: date
    closed_periods: List[str]   # e.g., ["2025-12", "2026-01"] as YYYY-MM strings


# -----------------------------
# Helpers
# -----------------------------

def _to_date(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d


def _period_key(d: date) -> str:
    # YYYY-MM
    return f"{d.year:04d}-{d.month:02d}"


def _override_matches(required_type: str, ov: Optional[CalendarOverride]) -> bool:
    if ov is None:
        return False
    if ov.override_type != required_type:
        return False
    if not ov.override_reason or not ov.override_reason.strip():
        return False
    if not ov.override_by_user_id or not ov.override_by_user_id.strip():
        return False
    if not ov.override_ticket_ref or not ov.override_ticket_ref.strip():
        return False
    return True


# -----------------------------
# Engine
# -----------------------------

class PostingCalendarEngine:
    def __init__(self, policy: PostingCalendarPolicy):
        self.policy = policy

    def validate_execution_date(
        self,
        execution_date: date | datetime,
        today: date | datetime,
        override: Optional[CalendarOverride],
    ) -> CalendarDecision:
        exec_d = _to_date(execution_date)
        today_d = _to_date(today)

        # Rule: cannot post before go-live
        if exec_d < self.policy.system_go_live_date:
            required = "PRE_GO_LIVE_POST"
            if _override_matches(required, override):
                return CalendarDecision(
                    status="ALLOW",
                    reason_code="ALLOW_PRE_GO_LIVE_WITH_OVERRIDE",
                    message="Execution date is before go-live date; override supplied.",
                    meta={"execution_date": str(exec_d), "go_live_date": str(self.policy.system_go_live_date)},
                )
            return CalendarDecision(
                status="OVERRIDE_REQUIRED",
                reason_code="EXEC_BEFORE_GO_LIVE",
                message="Cannot post before system go-live date unless override is supplied.",
                required_override_type=required,
                meta={"execution_date": str(exec_d), "go_live_date": str(self.policy.system_go_live_date)},
            )

        # Rule: cannot post to a past execution date unless override
        if exec_d < today_d:
            required = "BACKDATE_EXECUTION_DATE"
            if _override_matches(required, override):
                return CalendarDecision(
                    status="ALLOW",
                    reason_code="ALLOW_BACKDATED_EXEC_WITH_OVERRIDE",
                    message="Backdated execution date; override supplied.",
                    meta={"execution_date": str(exec_d), "today": str(today_d)},
                )
            return CalendarDecision(
                status="OVERRIDE_REQUIRED",
                reason_code="EXEC_BACKDATED",
                message="Cannot post to a past execution date unless override is supplied.",
                required_override_type=required,
                meta={"execution_date": str(exec_d), "today": str(today_d)},
            )

        return CalendarDecision(
            status="ALLOW",
            reason_code="ALLOW_EXEC_DATE_OK",
            message="Execution date is valid.",
            meta={"execution_date": str(exec_d), "today": str(today_d)},
        )

    def validate_value_date(
        self,
        value_date: date | datetime,
        execution_date: date | datetime,
        override: Optional[CalendarOverride],
    ) -> CalendarDecision:
        val_d = _to_date(value_date)
        exec_d = _to_date(execution_date)

        # Rule: value date can be same day or future date (allowed)
        if val_d >= exec_d:
            return CalendarDecision(
                status="ALLOW",
                reason_code="ALLOW_VALUE_DATE_OK",
                message="Value date is same-day or future date (allowed).",
                meta={"value_date": str(val_d), "execution_date": str(exec_d)},
            )

        # Rule: past value date requires override
        required = "BACKDATE_VALUE_DATE"
        if _override_matches(required, override):
            return CalendarDecision(
                status="ALLOW",
                reason_code="ALLOW_BACKDATED_VALUE_WITH_OVERRIDE",
                message="Backdated value date; override supplied.",
                meta={"value_date": str(val_d), "execution_date": str(exec_d)},
            )

        return CalendarDecision(
            status="OVERRIDE_REQUIRED",
            reason_code="VALUE_BACKDATED",
            message="Cannot back-date value date unless override is supplied.",
            required_override_type=required,
            meta={"value_date": str(val_d), "execution_date": str(exec_d)},
        )

    def validate_closed_period(
        self,
        execution_date: date | datetime,
        override: Optional[CalendarOverride],
    ) -> CalendarDecision:
        exec_d = _to_date(execution_date)
        period = _period_key(exec_d)

        if period in set(self.policy.closed_periods):
            required = "CLOSED_PERIOD_POST"
            if _override_matches(required, override):
                return CalendarDecision(
                    status="ALLOW",
                    reason_code="ALLOW_CLOSED_PERIOD_WITH_OVERRIDE",
                    message="Posting into a closed period; override supplied.",
                    meta={"execution_date": str(exec_d), "period": period},
                )
            return CalendarDecision(
                status="OVERRIDE_REQUIRED",
                reason_code="CLOSED_PERIOD_BLOCK",
                message="Cannot post into a closed financial period unless override is supplied.",
                required_override_type=required,
                meta={"execution_date": str(exec_d), "period": period},
            )

        return CalendarDecision(
            status="ALLOW",
            reason_code="ALLOW_PERIOD_OPEN",
            message="Financial period is open.",
            meta={"execution_date": str(exec_d), "period": period},
        )

    def validate_posting_window(
        self,
        execution_date: date | datetime,
        value_date: date | datetime,
        today: date | datetime,
        override: Optional[CalendarOverride],
    ) -> CalendarDecision:
        """
        Orchestrator: evaluate execution-date rules, closed period rules, value-date rules.
        Fail-closed on first OVERRIDE_REQUIRED / BLOCK.
        """

        d1 = self.validate_execution_date(execution_date, today, override)
        if d1.status != "ALLOW":
            return d1

        d2 = self.validate_closed_period(execution_date, override)
        if d2.status != "ALLOW":
            return d2

        d3 = self.validate_value_date(value_date, execution_date, override)
        if d3.status != "ALLOW":
            return d3

        return CalendarDecision(
            status="ALLOW",
            reason_code="ALLOW_POSTING_WINDOW_OK",
            message="Posting window validated successfully.",
            meta={
                "execution_date": str(_to_date(execution_date)),
                "value_date": str(_to_date(value_date)),
                "today": str(_to_date(today)),
            },
        )


# -----------------------------
# Policy loader (simple default)
# -----------------------------

def default_posting_calendar_policy() -> PostingCalendarPolicy:
    """
    Safe defaults for development.
    You can later load from config JSON controlled by Super User.
    """
    return PostingCalendarPolicy(
        system_go_live_date=date(2026, 1, 1),
        closed_periods=[],
    )