"""
Immutable Journal (Phase 14)

Non-negotiable controls:
- Account balances are NEVER manually editable.
- Every balance movement must be caused by a journaled transaction.
- Journal entries must be traceable by: ticket_id, user_id, timestamp, and line refs.
- Daily journal can be printed/exported per user (maker/checker/system).

This module is the ONLY permitted gateway to change balances.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from .account_registry import apply_delta, get_or_create_sub_account


# -----------------------------
# Journal model
# -----------------------------

@dataclass(frozen=True)
class JournalLine:
    journal_id: str
    ticket_id: str
    user_id: str
    action: str  # e.g. "posting_result_execute"
    at_utc: str  # ISO timestamp
    base_account_no: str
    account_type_code: str
    currency: str
    side: str  # DR or CR
    amount: float  # positive
    delta: float   # signed (+ for DR, - for CR)
    narrative: str
    meta: Dict[str, Any]


# Immutable append-only journal store (Phase 14: swap for DB/WORM storage)
_JOURNAL: List[JournalLine] = []
_NEXT_ID = 1


def _now_utc() -> str:
    return datetime.utcnow().isoformat()


def _next_journal_id() -> str:
    global _NEXT_ID
    jid = f"J-{_NEXT_ID:09d}"
    _NEXT_ID += 1
    return jid


def post_line(
    *,
    ticket_id: str,
    user_id: str,
    action: str,
    base_account_no: str,
    account_type_code: str,
    currency: str,
    side: str,
    amount: float,
    narrative: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Posts ONE journal line and applies delta to the appropriate sub-account.

    side rules:
    - DR increases balance (delta = +amount)
    - CR decreases balance (delta = -amount)

    IMPORTANT:
    - amount must be positive
    - currency must be full-text uppercase (enforced by account_registry)
    """
    s = (side or "").strip().upper()
    if s not in {"DR", "CR"}:
        raise ValueError("side must be DR or CR")

    amt = float(amount)
    if amt <= 0:
        raise ValueError("amount must be > 0")

    delta = amt if s == "DR" else -amt
    at = _now_utc()
    jid = _next_journal_id()

    # Ensure sub-account exists (creation is allowed; balance edits are only via delta)
    get_or_create_sub_account(base_account_no, account_type_code, currency)

    # Apply delta through registry (this is still not a manual change; it's journal-driven)
    sa = apply_delta(
        base_account_no,
        account_type_code,
        currency,
        delta,
        meta={
            "journal_id": jid,
            "ticket_id": ticket_id,
            "user_id": user_id,
            "action": action,
            "side": s,
            "amount": amt,
        },
    )

    jl = JournalLine(
        journal_id=jid,
        ticket_id=ticket_id,
        user_id=user_id,
        action=action,
        at_utc=at,
        base_account_no=sa.base_account_no,
        account_type_code=sa.account_type_code,
        currency=sa.currency,
        side=s,
        amount=amt,
        delta=delta,
        narrative=narrative or "",
        meta=meta or {},
    )
    _JOURNAL.append(jl)

    return {
        "journal_id": jid,
        "posted_at": at,
        "sub_account_id": sa.sub_account_id,
        "new_balance": sa.balance,
        "delta": delta,
    }


def list_journal_lines(
    *,
    for_date_utc: Optional[str] = None,  # YYYY-MM-DD (UTC day)
    user_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns journal lines filtered by UTC date and/or user_id and/or ticket_id.
    """
    def match(jl: JournalLine) -> bool:
        if for_date_utc:
            # jl.at_utc begins with YYYY-MM-DD
            if not jl.at_utc.startswith(for_date_utc):
                return False
        if user_id and jl.user_id != user_id:
            return False
        if ticket_id and jl.ticket_id != ticket_id:
            return False
        return True

    return [asdict(jl) for jl in _JOURNAL if match(jl)]


def daily_user_journal_report(user_id: str, for_date_utc: Optional[str] = None) -> Dict[str, Any]:
    """
    "Print" / export a daily journal report per signed-on user (UTC day).
    If for_date_utc omitted, defaults to today's UTC date.
    """
    if not for_date_utc:
        for_date_utc = date.today().isoformat()

    lines = list_journal_lines(for_date_utc=for_date_utc, user_id=user_id)

    total_count = len(lines)
    total_dr = sum(float(l["amount"]) for l in lines if l["side"] == "DR")
    total_cr = sum(float(l["amount"]) for l in lines if l["side"] == "CR")

    return {
        "report_type": "daily_user_journal",
        "user_id": user_id,
        "date_utc": for_date_utc,
        "total_lines": total_count,
        "total_dr": total_dr,
        "total_cr": total_cr,
        "lines": lines,
        "note": "Immutable journal; balances are changed only through these lines.",
    }
