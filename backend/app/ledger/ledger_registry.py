"""
Ledger Registry – Phase 14
Capital Strata Systems

Bridges Posting Approval → Journal → GL
"""

from decimal import Decimal
from typing import List
from .journal import JournalRegistry
from .general_ledger import GeneralLedger
from ..posting_contracts import PostingTicket


_JOURNAL = JournalRegistry()
_GL = GeneralLedger()


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


def trial_balance():
    return _GL.trial_balance()