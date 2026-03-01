"""
Posting Calendar Governance Engine – Phase 24B
Now reads real financial calendar configuration.

Enforces:
- No pre-go-live posting
- No backdated execution without override
- No backdated value without override
- No posting into CLOSED financial period without override
- Must be within defined financial year
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json


FINANCIAL_CALENDAR_FILE = Path("backend/app/config/financial_calendar.json")


@dataclass(frozen=True)
class CalendarOverride:
    override_type: str
    override_reason: str
    override_by_user_id: str
    override_ticket_ref: str


@dataclass(frozen=True)
class CalendarDecision:
    status: str
    reason_code: str
    message: str
    required_override_type: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


def _to_date(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d


def _period_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _override_matches(required_type: str, ov: Optional[CalendarOverride]) -> bool:
    if ov is None:
        return False
    return (
        ov.override_type == required_type
        and ov.override_reason
        and ov.override_by_user_id
        and ov.override_ticket_ref
    )


def _load_financial_calendar() -> Dict[str, Any]:
    if not FINANCIAL_CALENDAR_FILE.exists():
        raise FileNotFoundError("financial_calendar.json missing.")
    return json.loads(FINANCIAL_CALENDAR_FILE.read_text(encoding="utf-8"))


class PostingCalendarEngine:

    def __init__(self, system_go_live_date: date = date(2026, 1, 1)):
        self.system_go_live_date = system_go_live_date
        self.calendar = _load_financial_calendar()

    def validate_posting_window(
        self,
        execution_date: date,
        value_date: date,
        today: date,
        override: Optional[CalendarOverride],
    ) -> CalendarDecision:

        exec_d = _to_date(execution_date)
        val_d = _to_date(value_date)

        # Pre-go-live rule
        if exec_d < self.system_go_live_date:
            required = "PRE_GO_LIVE_POST"
            if _override_matches(required, override):
                return CalendarDecision("ALLOW", "ALLOW_PRE_GO_LIVE_WITH_OVERRIDE", "Override accepted.")
            return CalendarDecision(
                "OVERRIDE_REQUIRED",
                "EXEC_BEFORE_GO_LIVE",
                "Cannot post before system go-live date.",
                required_override_type=required,
            )

        # Financial year boundaries
        fy = self.calendar["financial_year"]
        fy_start = datetime.strptime(fy["start_date"], "%Y-%m-%d").date()
        fy_end = datetime.strptime(fy["end_date"], "%Y-%m-%d").date()

        if exec_d < fy_start or exec_d > fy_end:
            return CalendarDecision(
                "BLOCK",
                "OUTSIDE_FINANCIAL_YEAR",
                "Execution date outside active financial year."
            )

        # Closed period rule
        period = _period_key(exec_d)
        period_status = self.calendar["periods"].get(period, "OPEN")

        if period_status == "CLOSED":
            required = "CLOSED_PERIOD_POST"
            if _override_matches(required, override):
                return CalendarDecision("ALLOW", "ALLOW_CLOSED_PERIOD_OVERRIDE", "Override accepted.")
            return CalendarDecision(
                "OVERRIDE_REQUIRED",
                "CLOSED_PERIOD_BLOCK",
                f"Financial period {period} is CLOSED.",
                required_override_type=required,
            )

        # Backdated execution rule
        if exec_d < today:
            required = "BACKDATE_EXECUTION_DATE"
            if _override_matches(required, override):
                pass
            else:
                return CalendarDecision(
                    "OVERRIDE_REQUIRED",
                    "EXEC_BACKDATED",
                    "Backdated execution date requires override.",
                    required_override_type=required,
                )

        # Backdated value rule
        if val_d < exec_d:
            required = "BACKDATE_VALUE_DATE"
            if _override_matches(required, override):
                pass
            else:
                return CalendarDecision(
                    "OVERRIDE_REQUIRED",
                    "VALUE_BACKDATED",
                    "Backdated value date requires override.",
                    required_override_type=required,
                )

        return CalendarDecision(
            "ALLOW",
            "ALLOW_POSTING_WINDOW_OK",
            "Posting window validated successfully.",
            meta={"period": period}
        )