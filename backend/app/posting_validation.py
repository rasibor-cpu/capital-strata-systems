"""
Posting Validation Rules (Phase 13.3)

Pure validation logic for posting tickets.
NO execution. NO persistence.
"""

from typing import List
from datetime import datetime

from .posting_contracts import PostingTicket, PostingLine, ticket_totals


ALLOWED_SIDES = {"DR", "CR"}


def validate_dates(ticket: PostingTicket) -> List[str]:
    errors: List[str] = []

    for label, value in [("execution_date", ticket.execution_date), ("value_date", ticket.value_date)]:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except Exception:
            errors.append(f"{label} must be in YYYY-MM-DD format")

    return errors


def validate_lines(ticket: PostingTicket) -> List[str]:
    errors: List[str] = []

    if not ticket.lines:
        errors.append("Ticket must contain at least one posting line")

    for idx, ln in enumerate(ticket.lines):
        if ln.side.upper() not in ALLOWED_SIDES:
            errors.append(f"Line {idx}: side must be DR or CR")

        if ln.amount <= 0:
            errors.append(f"Line {idx}: amount must be greater than zero")

        if not ln.currency or ln.currency.upper() != ln.currency:
            errors.append(
                f"Line {idx}: currency must be full text uppercase (e.g., 'UNITED STATES DOLLAR')"
            )

        if not ln.account_no:
            errors.append(f"Line {idx}: account_no is required")

    return errors


def validate_balancing(ticket: PostingTicket) -> List[str]:
    totals = ticket_totals(ticket)
    if not totals["balanced"]:
        return [f"Ticket not balanced (DR={totals['dr_total']}, CR={totals['cr_total']})"]
    return []


def validate_ticket(ticket: PostingTicket) -> List[str]:
    errors: List[str] = []
    errors.extend(validate_dates(ticket))
    errors.extend(validate_lines(ticket))
    errors.extend(validate_balancing(ticket))
    return errors
