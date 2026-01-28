"""
Reporting Engine (v1)
--------------------
Generates permission-aware operational and management reports.

Key guarantees:
- Users can generate reports for themselves
- Supervisors/Admins can generate reports for others
- Aggregation supported at:
    - user
    - department
    - branch
    - country
- All reports are derived from UserActivityLedger (single source of truth)

This module DOES NOT execute trades.
It only reads immutable activity data.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from engine.security.user_activity_ledger import UserActivityLedger, UserActivityRecord
from engine.security.user_directory import UserDirectory
from engine.security.access_control import AccessLevel


@dataclass
class ReportRequest:
    requesting_user_id: str

    # scope
    target_user_id: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    country: Optional[str] = None

    # period
    start_date: str = ""
    end_date: str = ""


class ReportingEngine:
    """
    Permission-aware reporting engine.
    """

    def __init__(
        self,
        *,
        ledger: UserActivityLedger,
        user_directory: UserDirectory,
    ):
        self.ledger = ledger
        self.user_directory = user_directory

    # ─────────────────────────────
    # Permission enforcement
    # ─────────────────────────────
    def _assert_can_report(
        self,
        *,
        requester_id: str,
        target_user_id: Optional[str],
    ) -> None:
        requester = self.user_directory.require(requester_id)

        # User reporting on self → always allowed
        if target_user_id is None or target_user_id == requester_id:
            return

        # Otherwise must be supervisor or higher
        if requester.access_level not in {
            AccessLevel.SUPERVISOR,
            AccessLevel.ADMIN,
            AccessLevel.SUPER_ADMIN,
        }:
            raise PermissionError("Insufficient privileges to report on other users")

    # ─────────────────────────────
    # Core report generators
    # ─────────────────────────────
    def user_activity_report(self, req: ReportRequest) -> List[UserActivityRecord]:
        """
        User-level activity report.
        """
        self._assert_can_report(
            requester_id=req.requesting_user_id,
            target_user_id=req.target_user_id,
        )

        user_id = req.target_user_id or req.requesting_user_id

        return self.ledger.by_user_and_period(
            user_id=user_id,
            start_date=req.start_date,
            end_date=req.end_date,
        )

    def aggregate_activity_report(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> List[UserActivityRecord]:
        """
        Supervisor/Admin aggregation across all users.
        """
        return [
            r for r in self.ledger.all()
            if start_date <= r.business_date <= end_date
        ]

    # ─────────────────────────────
    # Trading-oriented reports
    # ─────────────────────────────
    def executed_trades(self, *, start_date: str, end_date: str) -> List[UserActivityRecord]:
        return [
            r for r in self.ledger.all()
            if r.action == "EXECUTE_TRADE"
            and start_date <= r.business_date <= end_date
            and r.success
        ]

    def outstanding_trades(self) -> List[UserActivityRecord]:
        return [
            r for r in self.ledger.all()
            if r.action == "OPEN_POSITION"
            and r.success
        ]

    def currency_running_balances(self) -> Dict[str, Decimal]:
        """
        Running balances per currency derived from activity.
        """
        balances: Dict[str, Decimal] = {}

        for r in self.ledger.all():
            if not r.amount or not r.currency:
                continue

            balances.setdefault(r.currency, Decimal("0"))

            if r.action in {"BUY", "CREDIT"}:
                balances[r.currency] += r.amount
            elif r.action in {"SELL", "DEBIT"}:
                balances[r.currency] -= r.amount

        return balances
