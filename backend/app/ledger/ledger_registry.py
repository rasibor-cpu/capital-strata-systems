"""
Ledger Registry – Phase 14c.0
Capital Strata Systems

Persistent Journal + Rebuildable GL + user metadata.
"""

from decimal import Decimal
from typing import Dict, Optional
from .journal import JournalRegistry
from .general_ledger import GeneralLedger
from ..posting_contracts import PostingTicket


_JOURNAL = JournalRegistry()
_GL = GeneralLedger()


def _rebuild_gl() -> None:
    for entry in _JOURNAL.all():
        _GL.apply(entry)


_rebuild_gl()


def post(
    ticket: PostingTicket,
    *,
    maker_user_id: Optional[str] = None,
    checker_user_id: Optional[str] = None,
    unit: Optional[str] = None,
):
    """
    Posts an APPROVED ticket into the persistent journal and updates GL in real time.
    """

    if ticket.status.value != "approved":
        raise ValueError("Ticket must be approved before ledger posting.")

    # Best-effort: if caller didn’t pass maker_user_id, infer from ticket
    inferred_maker = maker_user_id or getattr(ticket, "created_by", None)

    for line in ticket.lines:
        entry = _JOURNAL.append(
            ticket_id=ticket.ticket_id,
            execution_date=ticket.execution_date,
            account_no=line.account_no,
            side=line.side,
            amount=Decimal(str(line.amount)),
            currency=line.currency,
            maker_user_id=inferred_maker,
            checker_user_id=checker_user_id,
            unit=unit,
        )
        _GL.apply(entry)

    return {
        "journal_entries": len(ticket.lines),
        "gl_accounts_updated": len(ticket.lines),
        "maker_user_id": inferred_maker,
        "checker_user_id": checker_user_id,
        "unit": unit,
    }


def trial_balance() -> Dict[str, Decimal]:
    return _GL.trial_balance()