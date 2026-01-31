"""
postings/maker_ticket.py
------------------------
Maker Ticket "screen logic" (UI-agnostic).

Purpose:
- Define the input contract a UI will send (web/mobile)
- Validate fields consistently
- Call PostingStore.create_ticket(...) to create a PostingTicket

Notes:
- Customer onboarding + mandate enforcement will be added as hooks.
- For now, this module focuses on: validation + ticket creation.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any

from postings.api import PostingStore
from postings.models import PostingTicket, PostingType


@dataclass
class MakerTicketInput:
    posting_type: str
    amount: str
    currency: str
    debit_account: str
    credit_account: str
    maker_user: str
    description: str = ""
    approval_level_required: int = 0  # 0..5


def _parse_decimal(amount_str: str) -> Decimal:
    s = (amount_str or "").strip().replace(",", "")
    if not s:
        raise ValueError("amount is required")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError("amount must be a valid number")
    if d <= Decimal("0"):
        raise ValueError("amount must be > 0")
    return d.quantize(Decimal("0.01"))


def _normalize_ccy(ccy: str) -> str:
    c = (ccy or "").strip().upper()
    if len(c) != 3:
        raise ValueError("currency must be a 3-letter code (e.g., USD)")
    return c


def _normalize_posting_type(pt: str) -> PostingType:
    p = (pt or "").strip().upper()
    try:
        return PostingType[p]
    except KeyError:
        allowed = ", ".join([x.name for x in PostingType])
        raise ValueError(f"posting_type must be one of: {allowed}")


def validate_maker_input(inp: MakerTicketInput) -> None:
    if not (inp.maker_user or "").strip():
        raise ValueError("maker_user is required")

    if not (inp.debit_account or "").strip():
        raise ValueError("debit_account is required")

    if not (inp.credit_account or "").strip():
        raise ValueError("credit_account is required")

    if inp.debit_account.strip() == inp.credit_account.strip():
        raise ValueError("debit_account and credit_account must differ")

    _ = _normalize_posting_type(inp.posting_type)
    _ = _parse_decimal(inp.amount)
    _ = _normalize_ccy(inp.currency)

    lvl = int(inp.approval_level_required)
    if lvl < 0 or lvl > 5:
        raise ValueError("approval_level_required must be between 0 and 5")


def create_maker_ticket(
    store: PostingStore,
    inp: MakerTicketInput,
    *,
    customer_id: Optional[str] = None,
) -> PostingTicket:
    """
    UI calls this to create a DRAFT ticket.

    customer_id is reserved for the next phase:
    - enforce customer onboarding
    - enforce APPROVED signature mandate before allowing SUBMIT
    """
    validate_maker_input(inp)

    ticket = store.create_ticket(
        posting_type=_normalize_posting_type(inp.posting_type),
        amount=_parse_decimal(inp.amount),
        currency=_normalize_ccy(inp.currency),
        debit_account=inp.debit_account.strip(),
        credit_account=inp.credit_account.strip(),
        maker_user=inp.maker_user.strip(),
        description=(inp.description or "").strip(),
        approval_level_required=int(inp.approval_level_required),
    )
    return ticket


def input_from_dict(d: Dict[str, Any]) -> MakerTicketInput:
    """
    Convenience for UI payloads.
    """
    return MakerTicketInput(
        posting_type=str(d.get("posting_type", "")),
        amount=str(d.get("amount", "")),
        currency=str(d.get("currency", "")),
        debit_account=str(d.get("debit_account", "")),
        credit_account=str(d.get("credit_account", "")),
        maker_user=str(d.get("maker_user", "")),
        description=str(d.get("description", "")),
        approval_level_required=int(d.get("approval_level_required", 0)),
    )
