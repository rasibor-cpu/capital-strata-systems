"""
User Activity Ledger (v1)
------------------------
Authoritative append-only ledger of all user actions.

Design principles:
- Every action is immutable once recorded
- Every record is tied to:
    user_id
    session_id
    business_date
- Supports:
    - per-user reports
    - supervisor/admin aggregation
    - audit & compliance reconstruction
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal


@dataclass(frozen=True)
class UserActivityRecord:
    timestamp_utc: str
    business_date: str

    user_id: str
    session_id: str

    screen: str
    action: str
    resource: str

    amount: Optional[Decimal] = None
    currency: Optional[str] = None

    success: bool = True
    meta: Optional[Dict] = None


class UserActivityLedger:
    """
    In-memory append-only activity ledger (v1).

    NOTE:
    - v2 will persist to DB / object storage
    - interface is intentionally stable
    """

    def __init__(self):
        self._records: List[UserActivityRecord] = []

    # ─────────────────────────────
    # Core write operation
    # ─────────────────────────────
    def record(
        self,
        *,
        business_date: str,
        user_id: str,
        session_id: str,
        screen: str,
        action: str,
        resource: str,
        amount: Optional[Decimal] = None,
        currency: Optional[str] = None,
        success: bool = True,
        meta: Optional[Dict] = None,
    ) -> None:
        rec = UserActivityRecord(
            timestamp_utc=datetime.utcnow().isoformat(),
            business_date=business_date,
            user_id=user_id,
            session_id=session_id,
            screen=screen,
            action=action,
            resource=resource,
            amount=amount,
            currency=currency,
            success=success,
            meta=meta,
        )
        self._records.append(rec)

    # ─────────────────────────────
    # Query helpers (read-only)
    # ─────────────────────────────
    def all(self) -> List[UserActivityRecord]:
        return list(self._records)

    def by_user(self, *, user_id: str) -> List[UserActivityRecord]:
        return [r for r in self._records if r.user_id == user_id]

    def by_business_date(self, *, business_date: str) -> List[UserActivityRecord]:
        return [r for r in self._records if r.business_date == business_date]

    def by_user_and_period(
        self,
        *,
        user_id: str,
        start_date: str,
        end_date: str,
    ) -> List[UserActivityRecord]:
        return [
            r for r in self._records
            if r.user_id == user_id
            and start_date <= r.business_date <= end_date
        ]

    # ─────────────────────────────
    # Export helpers (for reports)
    # ─────────────────────────────
    def as_dicts(self) -> List[Dict]:
        return [asdict(r) for r in self._records]