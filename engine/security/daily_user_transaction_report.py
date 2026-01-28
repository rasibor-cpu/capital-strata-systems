"""
Daily User Transaction Report (v1)
----------------------------------
Generates transaction activity reports from UserActivityLedger.

Rules:
- User can generate report for self
- Supervisor/Admin can generate reports for other users
- Output is export-ready rows (list[dict]) for CSV/JSON

Included data (v1):
- executed trades
- open/close positions
- credits/debits
- counterparty + settlement fields when present in meta
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from engine.security.user_activity_ledger import UserActivityLedger, UserActivityRecord
from engine.security.user_directory import UserDirectory
from engine.security.rbac import AccessLevel
from engine.security.trade_event_vocabulary import TradeEvent


@dataclass
class DailyTxnReportRequest:
    requesting_user_id: str
    start_date: str
    end_date: str
    target_user_id: Optional[str] = None


class DailyUserTransactionReport:
    def __init__(self, *, ledger: UserActivityLedger, users: UserDirectory):
        self.ledger = ledger
        self.users = users

    def _assert_allowed(self, req: DailyTxnReportRequest) -> None:
        # Self always allowed
        if req.target_user_id is None or req.target_user_id == req.requesting_user_id:
            return

        requester = self.users.require(req.requesting_user_id)
        if requester.access_level not in {
            AccessLevel.LEVEL_3_SUPERVISOR,
            AccessLevel.LEVEL_4_ADMIN,
        }:
            raise PermissionError("Insufficient privileges to report on other users")

    def generate_rows(self, req: DailyTxnReportRequest) -> List[Dict[str, Any]]:
        self._assert_allowed(req)

        uid = req.target_user_id or req.requesting_user_id

        records = self.ledger.by_user_and_period(
            user_id=uid,
            start_date=req.start_date,
            end_date=req.end_date,
        )

        # Only transaction-relevant actions
        txn_actions = {
            TradeEvent.EXECUTE_TRADE.value,
            TradeEvent.OPEN_POSITION.value,
            TradeEvent.CLOSE_POSITION.value,
            TradeEvent.BUY.value,
            TradeEvent.SELL.value,
            TradeEvent.CREDIT.value,
            TradeEvent.DEBIT.value,
            TradeEvent.ORDER_SUBMITTED.value,
            TradeEvent.ORDER_CANCELLED.value,
        }

        rows: List[Dict[str, Any]] = []

        for r in records:
            if r.action not in txn_actions:
                continue
            rows.append(self._row_from_record(r))

        return rows

    def _row_from_record(self, r: UserActivityRecord) -> Dict[str, Any]:
        meta = r.meta or {}
        return {
            "business_date": r.business_date,
            "timestamp_utc": r.timestamp_utc,
            "user_id": r.user_id,
            "session_id": r.session_id,
            "screen": r.screen,
            "action": r.action,
            "resource": r.resource,
            "amount": str(r.amount) if r.amount is not None else None,
            "currency": r.currency,
            "success": r.success,
            # settlement/audit identifiers
            "counterparty": meta.get("counterparty"),
            "account_name": meta.get("account_name"),
            "account_number": meta.get("account_number"),
            "sort_code": meta.get("sort_code"),
            "routing_code": meta.get("routing_code"),
            "branch": meta.get("branch"),
            "department": meta.get("department"),
            "country": meta.get("country"),
            "notes": meta.get("notes"),
        }