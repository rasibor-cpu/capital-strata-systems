"""
posting_ledger.py — Customer Posting Ledger (Governance-Grade)
--------------------------------------------------------------
Purpose:
- Record customer-related postings (DR/CR, FX, transfers, adjustments)
- Maintain customer + ledger + transaction context
- Enable breach reports to carry full posting details

Design:
- Append-only
- Deterministic
- No execution / no settlement
- Sale-grade audit clarity
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from datetime import datetime
import uuid


# -----------------------------
# Posting Entry
# -----------------------------

@dataclass
class PostingEntry:
    entry_id: str
    customer_id: str
    customer_name: str
    account_ref: str

    ledger_type: str           # CUSTOMER / TREASURY / INTERNAL
    ledger_id: str

    transaction_type: str      # POSTING / TRANSFER / FX / ADJUSTMENT
    side: str                  # DR / CR
    currency: str              # e.g. USD, NGN, EUR
    notional: float
    fx_pair: Optional[str]     # e.g. USDNGN (if FX)
    price: Optional[float]

    value_date: Optional[str]
    booking_date: str
    description: str


# -----------------------------
# Customer Posting Ledger
# -----------------------------

class PostingLedger:
    def __init__(self):
        self.entries: List[PostingEntry] = []

    def post(
        self,
        customer_id: str,
        customer_name: str,
        account_ref: str,
        ledger_type: str,
        ledger_id: str,
        transaction_type: str,
        side: str,
        currency: str,
        notional: float,
        description: str,
        fx_pair: Optional[str] = None,
        price: Optional[float] = None,
        value_date: Optional[str] = None,
    ) -> PostingEntry:

        entry = PostingEntry(
            entry_id=str(uuid.uuid4()),
            customer_id=customer_id,
            customer_name=customer_name,
            account_ref=account_ref,
            ledger_type=ledger_type,
            ledger_id=ledger_id,
            transaction_type=transaction_type,
            side=side,
            currency=currency,
            notional=notional,
            fx_pair=fx_pair,
            price=price,
            value_date=value_date,
            booking_date=datetime.utcnow().isoformat(),
            description=description,
        )
        self.entries.append(entry)
        return entry

    def snapshot(self) -> List[Dict]:
        return [asdict(e) for e in self.entries]
