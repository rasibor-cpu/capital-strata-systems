"""
Ledger Registry – Phase 15 (Dimensional Ledger)
Capital Strata Systems

Persistent Journal + Rebuildable GL + dimension bundle per entry.
"""

from decimal import Decimal
from typing import Dict, Optional, Any
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
    dims: Optional[dict[str, Any]] = None,
):
    if ticket.status.value != "approved":
        raise ValueError("Ticket must be approved before ledger posting.")

    inferred_maker = maker_user_id or getattr(ticket, "created_by", None)
    dims = dims or {}

    # Convenience mapping: allow ticket.unit/team/branch/division/country if present
    for k in ("unit", "team", "branch", "division", "country"):
        v = getattr(ticket, k, None)
        if v and k not in dims:
            dims[k] = v

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
            dims=dims,
        )
        _GL.apply(entry)

    return {
        "journal_entries": len(ticket.lines),
        "gl_accounts_updated": len(ticket.lines),
        "maker_user_id": inferred_maker,
        "checker_user_id": checker_user_id,
        "dims": dims,
    }


def trial_balance() -> Dict[str, Decimal]:
    return _GL.trial_balance()