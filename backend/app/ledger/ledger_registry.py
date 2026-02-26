"""
Ledger Registry – Phase 14b
Capital Strata Systems

Persistent Journal + Rebuildable GL
"""

from decimal import Decimal
from typing import Dict
from .journal import JournalRegistry
from .general_ledger import GeneralLedger
from ..posting_contracts import PostingTicket


_JOURNAL = JournalRegistry()
_GL = GeneralLedger()


# ------------------------------------------------------------
# Rebuild GL from persistent journal at startup
# ------------------------------------------------------------

def _rebuild_gl():
    for entry in _JOURNAL.all():
        _GL.apply(entry)


_rebuild_gl()


# ------------------------------------------------------------

def post(ticket: PostingTicket):

    if ticket.status.value != "approved":
        raise ValueError("Ticket must be approved before ledger posting.")

    for line in ticket.lines:

        entry = _JOURNAL.append(
            ticket_id=ticket.ticket_id,
            execution_date=ticket.execution_date,
            account_no=line.account_no,
            side=line.side,
            amount=Decimal(str(line.amount)),
            currency=line.currency,
        )

        _GL.apply(entry)

    return {
        "journal_entries": len(ticket.lines),
        "gl_accounts_updated": len(ticket.lines),
    }


def trial_balance() -> Dict[str, Decimal]:
    return _GL.trial_balance()