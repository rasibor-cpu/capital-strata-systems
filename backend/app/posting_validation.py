"""
Posting Validation Rules – Phase 14 (Currency Hardened)

Pure validation logic for posting tickets.
NO execution. NO persistence.

Enforces:
- ISO currency selection (dropdown driven)
- Minor unit precision control
- Balancing control
"""

from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import json

from .posting_contracts import PostingTicket, PostingLine, ticket_totals


ALLOWED_SIDES = {"DR", "CR"}

REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENCY_FILE = REPO_ROOT / "backend" / "app" / "config" / "currency_master.json"


# -------------------------------------------------------
# Currency Master Loader
# -------------------------------------------------------

def _load_currency_master() -> Dict[str, Any]:
    if not CURRENCY_FILE.exists():
        raise FileNotFoundError(
            f"Missing currency master file: {CURRENCY_FILE}"
        )
    return json.loads(CURRENCY_FILE.read_text(encoding="utf-8"))


# -------------------------------------------------------
# Date Validation
# -------------------------------------------------------

def validate_dates(ticket: PostingTicket) -> List[str]:
    errors: List[str] = []

    for label, value in [
        ("execution_date", ticket.execution_date),
        ("value_date", ticket.value_date),
    ]:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except Exception:
            errors.append(f"{label} must be in YYYY-MM-DD format")

    return errors


# -------------------------------------------------------
# Line Validation
# -------------------------------------------------------

def validate_lines(ticket: PostingTicket) -> List[str]:
    errors: List[str] = []

    if not ticket.lines:
        errors.append("Ticket must contain at least one posting line")

    currency_master = _load_currency_master()

    for idx, ln in enumerate(ticket.lines):

        # Side
        if ln.side.upper() not in ALLOWED_SIDES:
            errors.append(f"Line {idx}: side must be DR or CR")

        # Amount
        if ln.amount <= 0:
            errors.append(f"Line {idx}: amount must be greater than zero")

        # Account number
        if not ln.account_no:
            errors.append(f"Line {idx}: account_no is required")

        # Currency (dropdown enforced)
        if not ln.currency:
            errors.append(f"Line {idx}: currency is required")
            continue

        cur = ln.currency.strip().upper()

        if cur not in currency_master:
            errors.append(
                f"Line {idx}: currency '{cur}' is not in approved currency list"
            )
            continue

        # Enforce minor unit precision
        minor_unit = int(currency_master[cur].get("minor_unit", 2))

        try:
            amt = float(ln.amount)
        except Exception:
            errors.append(f"Line {idx}: amount must be numeric")
            continue

        if round(amt, minor_unit) != amt:
            errors.append(
                f"Line {idx}: amount exceeds allowed decimal precision for {cur} "
                f"(max {minor_unit} decimals)"
            )

    return errors


# -------------------------------------------------------
# Balancing Validation
# -------------------------------------------------------

def validate_balancing(ticket: PostingTicket) -> List[str]:
    totals = ticket_totals(ticket)
    if not totals["balanced"]:
        return [
            f"Ticket not balanced (DR={totals['dr_total']}, CR={totals['cr_total']})"
        ]
    return []


# -------------------------------------------------------
# Master Validation
# -------------------------------------------------------

def validate_ticket(ticket: PostingTicket) -> List[str]:
    errors: List[str] = []
    errors.extend(validate_dates(ticket))
    errors.extend(validate_lines(ticket))
    errors.extend(validate_balancing(ticket))
    return errors