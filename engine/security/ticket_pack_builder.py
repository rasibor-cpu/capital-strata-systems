"""
Ticket Pack Builder (v1)
------------------------
Builds transaction "tickets" suitable for:
- end-of-day batch review
- audit trail printouts
- export to CSV/JSON for printing systems

V1:
- Tickets are built from UserActivityLedger records.
- A ticket is one executed trade or posting-like event.
- Output is a structured list of dicts that can be exported.

Later:
- Printer integration
- PDF rendering
- Digital signatures
- Ticket sequencing & locking
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from engine.security.user_activity_ledger import UserActivityLedger, UserActivityRecord
from engine.security.trade_event_vocabulary import TradeEvent


@dataclass
class TicketRequest:
    business_date: str
    requesting_user_id: str

    # optional filters
    target_user_id: Optional[str] = None
    branch: Optional[str] = None
    department: Optional[str] = None
    country: Optional[str] = None


class TicketPackBuilder:
    def __init__(self, *, ledger: UserActivityLedger):
        self.ledger = ledger

    def _matches_filters(self, r: UserActivityRecord, req: TicketRequest) -> bool:
        if req.target_user_id and r.user_id != req.target_user_id:
            return False

        # v1: branch/department/country stored in meta tags if provided
        if req.branch and (not r.meta or r.meta.get("branch") != req.branch):
            return False
        if req.department and (not r.meta or r.meta.get("department") != req.department):
            return False
        if req.country and (not r.meta or r.meta.get("country") != req.country):
            return False

        return True

    def build_eod_ticket_pack(self, req: TicketRequest) -> List[Dict[str, Any]]:
        """
        Builds an EOD ticket pack for a specific business date.
        """

        records = [
            r for r in self.ledger.by_business_date(business_date=req.business_date)
            if self._matches_filters(r, req)
        ]

        # Ticket-worthy events (v1)
        ticket_events = {
            TradeEvent.EXECUTE_TRADE.value,
            TradeEvent.OPEN_POSITION.value,
            TradeEvent.CLOSE_POSITION.value,
            TradeEvent.BUY.value,
            TradeEvent.SELL.value,
            TradeEvent.CREDIT.value,
            TradeEvent.DEBIT.value,
        }

        tickets: List[Dict[str, Any]] = []
        seq = 1

        for r in records:
            if r.action not in ticket_events:
                continue

            tickets.append(
                {
                    "ticket_seq": seq,
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
                    "counterparty": (r.meta or {}).get("counterparty"),
                    "account_name": (r.meta or {}).get("account_name"),
                    "account_number": (r.meta or {}).get("account_number"),
                    "sort_code": (r.meta or {}).get("sort_code"),
                    "routing_code": (r.meta or {}).get("routing_code"),
                    "branch": (r.meta or {}).get("branch"),
                    "department": (r.meta or {}).get("department"),
                    "country": (r.meta or {}).get("country"),
                    "notes": (r.meta or {}).get("notes"),
                }
            )
            seq += 1

        return tickets