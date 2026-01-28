"""
Business Day Control (v1)
-------------------------
Defines business date and EOD lock.

Rules:
- Business date is explicit and independent of system date
- Once EOD is closed for a date, transactions for that date are blocked
- Only supervisor/admin should be allowed to run EOD (enforced via SecurityContext + RBAC)
- Every EOD action is audited
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from engine.security.audit_log import AuditLogger, AuditEventType


@dataclass(frozen=True)
class BusinessDayState:
    business_date: str               # YYYY-MM-DD
    opened_at_utc: str
    closed_at_utc: Optional[str] = None
    is_closed: bool = False
    closed_by_user_id: Optional[str] = None


class BusinessDayManager:
    def __init__(self, audit: AuditLogger):
        self.audit = audit
        self._days: Dict[str, BusinessDayState] = {}

    def open_day(self, *, business_date: str, opened_by_user_id: str, session_id: str) -> BusinessDayState:
        if business_date in self._days and self._days[business_date].is_closed:
            raise PermissionError("Cannot reopen a closed business day")

        now = datetime.utcnow().isoformat()
        state = BusinessDayState(
            business_date=business_date,
            opened_at_utc=now,
            closed_at_utc=None,
            is_closed=False,
            closed_by_user_id=None,
        )
        self._days[business_date] = state

        self.audit.log(
            event_type=AuditEventType.SYSTEM,
            user_id=opened_by_user_id,
            role=None,
            session_id=session_id,
            screen="EOD",
            action="OPEN_DAY",
            resource=business_date,
            success=True,
            meta={"business_date": business_date},
        )

        return state

    def close_day(self, *, business_date: str, closed_by_user_id: str, session_id: str) -> BusinessDayState:
        state = self._days.get(business_date)
        if not state:
            raise ValueError("Business day not opened")

        if state.is_closed:
            return state  # idempotent close

        now = datetime.utcnow().isoformat()
        closed = BusinessDayState(
            business_date=state.business_date,
            opened_at_utc=state.opened_at_utc,
            closed_at_utc=now,
            is_closed=True,
            closed_by_user_id=closed_by_user_id,
        )
        self._days[business_date] = closed

        self.audit.log(
            event_type=AuditEventType.SYSTEM,
            user_id=closed_by_user_id,
            role=None,
            session_id=session_id,
            screen="EOD",
            action="CLOSE_DAY",
            resource=business_date,
            success=True,
            meta={"business_date": business_date},
        )

        return closed

    def assert_day_open(self, business_date: str) -> None:
        state = self._days.get(business_date)
        if not state:
            raise PermissionError("Business day not opened")
        if state.is_closed:
            raise PermissionError("Business day is closed (EOD locked)")

    def get_state(self, business_date: str) -> Optional[BusinessDayState]:
        return self._days.get(business_date)