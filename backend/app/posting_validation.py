"""
Posting Validation Rules (Phase 17.x)

Pure validation logic for posting tickets.
NO execution. NO persistence.

Additions:
- 10-digit account governance:
  * Internal GL accounts MUST be 10 digits starting with "000" (accept dashed input)
  * Customer accounts MUST be 10 digits NOT starting with "000" (stored in customer_acct)
  * If a 10-digit customer-style account is provided in account_no -> FAIL (use customer_acct)
- Backward compatible:
  * Non-10-digit legacy account_no is still allowed (validation only checks presence),
    because some screens may still be using legacy identifiers during migration.
"""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from .posting_contracts import PostingTicket, PostingLine, ticket_totals


ALLOWED_SIDES = {"DR", "CR"}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _canon10(value: Optional[str]) -> Optional[str]:
    """
    Accept '0001-840-001' or '0001840001' -> '0001840001' if 10 digits.
    Returns None if not canonicalizable to 10 digits.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s2 = s.replace("-", "").replace(" ", "")
    if s2.isdigit() and len(s2) == 10:
        return s2
    return None


def _is_internal_gl(acct10: str) -> bool:
    return acct10.startswith("000")


def _currency_ok(cur: str) -> bool:
    """
    Accept:
    - Full-text uppercase currency names (legacy): 'UNITED STATES DOLLAR'
    - ISO alpha: 'USD'
    - ISO numeric: '840'
    """
    if not cur:
        return False
    c = cur.strip()
    if not c:
        return False

    # ISO numeric (3 digits)
    if c.isdigit() and len(c) == 3:
        return True

    # ISO alpha (3 letters)
    if len(c) == 3 and c.isalpha() and c.upper() == c:
        return True

    # Legacy: full text uppercase (spaces allowed)
    if c.upper() == c:
        return True

    return False


# ------------------------------------------------------------
# Validators
# ------------------------------------------------------------

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
        # side
        if (ln.side or "").upper() not in ALLOWED_SIDES:
            errors.append(f"Line {idx}: side must be DR or CR")

        # amount
        if ln.amount <= 0:
            errors.append(f"Line {idx}: amount must be greater than zero")

        # currency (expanded acceptance)
        if not _currency_ok(getattr(ln, "currency", "")):
            errors.append(
                f"Line {idx}: currency must be ISO alpha (e.g., 'USD'), ISO numeric (e.g., '840'), "
                f"or legacy full-text uppercase (e.g., 'UNITED STATES DOLLAR')"
            )

        # account_no required
        acct_no = getattr(ln, "account_no", None)
        if not acct_no:
            errors.append(f"Line {idx}: account_no is required")
        else:
            acct10 = _canon10(str(acct_no))
            if acct10 is not None:
                # If 10 digits, enforce internal GL rule for account_no
                if not _is_internal_gl(acct10):
                    errors.append(
                        f"Line {idx}: Invalid account_no for internal ledger. "
                        f"10-digit customer-style account detected ({acct10}). "
                        f"Internal GL accounts must start with '000'. "
                        f"Use customer_acct for customer ledger postings."
                    )

        # Optional governance fields on line (fail-closed only if present & 10-digit)
        cust = getattr(ln, "customer_acct", None)
        cust10 = _canon10(str(cust)) if cust else None
        if cust10 is not None and _is_internal_gl(cust10):
            errors.append(
                f"Line {idx}: customer_acct cannot start with '000' (internal-ledger prefix). "
                f"Got: {cust10}"
            )

        glid = getattr(ln, "gl_account_id", None)
        gl10 = _canon10(str(glid)) if glid else None
        if gl10 is not None and not _is_internal_gl(gl10):
            errors.append(
                f"Line {idx}: gl_account_id must start with '000' (internal-ledger prefix). "
                f"Got: {gl10}"
            )

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