"""
postings/ledger_adapter.py
-------------------------
Bridge: PostingTicket (maker-checker) -> PostingLedger (governance-grade).

Hard rules:
- Do NOT modify PostingTicket models
- PostingLedger remains the authoritative append-only sink
- Create exactly two ledger rows per approved ticket: DR + CR
- Enforce approval level requirements before posting

Key design:
- PostingLedger implementations vary (some accept PostingEntry objects, others accept
  explicit fields). We therefore:
    * detect the best available ledger method
    * inspect its signature
    * pass only the parameters it actually accepts (by name)
- This avoids hand-editing posting_ledger.py and avoids brittle coupling.

Expected fields (common across variants):
- ledger_type, ledger_id, domain, transaction_type, side, currency, notional, description,
  fx_pair, price, value_date, approved_by, approval_level
Plus (optional depending on implementation):
- customer_id, customer_name, account_ref, customer_type, booking_date, entry_id
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Callable, Tuple
import inspect

from postings.models import PostingTicket, PostingStatus
from posting_ledger import PostingLedger, APPROVAL_ORDER


# -----------------------------
# Helpers
# -----------------------------

def _require(condition: bool, msg: str) -> None:
    if not condition:
        raise ValueError(msg)


def _normalize_ccy(ccy: str) -> str:
    c = (ccy or "").strip().upper()
    _require(len(c) == 3, "currency must be a 3-letter code (e.g., USD)")
    return c


def _to_float_amount(amount: Decimal) -> float:
    _require(amount > Decimal("0"), "amount must be > 0")
    return float(amount.quantize(Decimal("0.01")))


def _approval_level_ok(required_level: int, approver_level: Optional[str]) -> bool:
    req = int(required_level)
    _require(0 <= req <= 5, "approval_level_required must be between 0 and 5")
    if req == 0:
        return True
    if not approver_level:
        return False
    got = APPROVAL_ORDER.get(approver_level.upper())
    return got is not None and got >= req


def _pick_ledger_method(ledger: PostingLedger) -> Tuple[str, Callable[..., Any]]:
    """
    Choose the best available method for appending/posting a ledger entry.

    We prefer a public method if present; otherwise fall back to _append_entry.
    """
    candidates = [
        "post_entry",
        "post",
        "append_entry",
        "add_entry",
        "record_entry",
        "_append_entry",
    ]
    for name in candidates:
        fn = getattr(ledger, name, None)
        if callable(fn):
            return name, fn
    raise ValueError("No suitable append/post method found on PostingLedger")


def _call_with_signature(fn: Callable[..., Any], kwargs: Dict[str, Any]) -> Any:
    """
    Call fn using only the kwargs it accepts.
    """
    sig = inspect.signature(fn)
    accepted = {}
    for k, v in kwargs.items():
        if k in sig.parameters:
            accepted[k] = v

    # Some implementations may only accept positional args; in that case,
    # we will try to supply parameters in-order using the signature.
    if accepted:
        return fn(**accepted)

    # Positional fallback (rare): build args in param order excluding "self"
    params = [p for p in sig.parameters.values() if p.name != "self"]
    args = []
    for p in params:
        if p.name in kwargs:
            args.append(kwargs[p.name])
        elif p.default is not inspect._empty:
            args.append(p.default)
        else:
            raise TypeError(f"Ledger method missing required arg: {p.name}")
    return fn(*args)


# -----------------------------
# Main adapter
# -----------------------------

def post_approved_ticket_to_ledger(
    *,
    ledger: PostingLedger,
    ticket: PostingTicket,
    customer_id: str,
    customer_name: str,
    account_ref: str,
    customer_type: str = "CUSTOMER",
    ledger_type: str = "CUSTOMER",
    domain: str = "TREASURY",
    transaction_type: str = "POSTING",
    fx_pair: Optional[str] = None,
    price: Optional[float] = None,
    value_date: Optional[str] = None,
    booking_date: Optional[str] = None,
    approver_level: Optional[str] = None,
) -> None:
    """
    Convert an APPROVED PostingTicket into two ledger entries (DR + CR)
    via the PostingLedger's own append/post API.

    Notes:
    - booking_date defaults to today's UTC date (YYYY-MM-DD)
    - value_date can be None for simple postings
    - ticket.mark_posted() is called only after both legs are posted
    """

    _require(ticket.status == PostingStatus.APPROVED, "ticket must be APPROVED before posting")
    _require(ticket.debit_account.strip() != "", "ticket.debit_account is required")
    _require(ticket.credit_account.strip() != "", "ticket.credit_account is required")
    _require(customer_id.strip() != "", "customer_id is required")
    _require(customer_name.strip() != "", "customer_name is required")
    _require(account_ref.strip() != "", "account_ref is required")

    _require(
        _approval_level_ok(ticket.approval_level_required, approver_level),
        "approval level insufficient for posting",
    )

    ccy = _normalize_ccy(ticket.currency)
    amt = _to_float_amount(ticket.amount)

    book_date = booking_date or datetime.utcnow().date().isoformat()
    desc = ticket.description.strip() or f"Posting ticket {ticket.ticket_id}"

    method_name, method = _pick_ledger_method(ledger)

    def _post_leg(*, side: str, ledger_id: str, entry_id: str) -> None:
        payload: Dict[str, Any] = {
            # Common governance fields
            "entry_id": entry_id,
            "customer_id": customer_id.strip(),
            "customer_name": customer_name.strip(),
            "account_ref": account_ref.strip(),
            "customer_type": customer_type.strip().upper(),
            "booking_date": book_date,

            # Ledger fields (commonly required)
            "ledger_type": ledger_type.strip().upper(),
            "ledger_id": ledger_id.strip(),
            "domain": domain.strip().upper(),

            # Transaction fields
            "transaction_type": transaction_type.strip().upper(),
            "side": side,
            "currency": ccy,
            "notional": amt,
            "description": desc,

            # Optional FX
            "fx_pair": fx_pair,
            "price": price,
            "value_date": value_date,

            # Approval metadata
            "approved_by": ticket.approver_user,
            "approval_level": (approver_level or "").upper() if approver_level else None,
        }

        # Some ledgers may want different naming; provide aliases safely.
        payload.setdefault("amount", amt)
        payload.setdefault("ccy", ccy)

        _call_with_signature(method, payload)

    # Post DR then CR
    _post_leg(side="DR", ledger_id=ticket.debit_account, entry_id=str(ticket.ticket_id) + "::DR")
    _post_leg(side="CR", ledger_id=ticket.credit_account, entry_id=str(ticket.ticket_id) + "::CR")

    # Mark ticket posted after successful ledger writes
    ticket.mark_posted()
