"""
posting_store.py
----------------
Posting validation + draft helpers used by posting lifecycle.

This module MUST expose:
- validate_posting_lines(payload_lines)

Design principles:
- Deterministic validation
- No ledger mutation here
- All actual posting happens in journal/ledger_registry
"""

from typing import List, Dict, Any


ALLOWED_SIDES = {"DR", "CR"}


def validate_posting_lines(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate posting lines for correctness before ticket creation.
    Enforces:
    - At least 2 lines
    - Each line has required fields
    - Side is DR/CR
    - Amount is positive numeric
    - Balanced totals (ΣDR = ΣCR)
    Returns a validation dict with totals and errors.
    Raises ValueError on failure (caller should catch if needed).
    """

    if not isinstance(lines, list) or len(lines) < 2:
        raise ValueError("Posting must contain at least 2 lines.")

    required = {"side", "base_account_no", "account_type_code", "currency", "amount", "narrative"}

    dr_total = 0.0
    cr_total = 0.0
    errors = []

    for i, ln in enumerate(lines):
        if not isinstance(ln, dict):
            errors.append(f"Line {i}: must be an object/dict.")
            continue

        missing = [k for k in required if k not in ln]
        if missing:
            errors.append(f"Line {i}: missing fields {missing}.")
            continue

        side = str(ln.get("side", "")).upper().strip()
        if side not in ALLOWED_SIDES:
            errors.append(f"Line {i}: side must be DR or CR.")
            continue

        try:
            amt = float(ln.get("amount", 0))
        except Exception:
            errors.append(f"Line {i}: amount must be numeric.")
            continue

        if amt <= 0:
            errors.append(f"Line {i}: amount must be > 0.")
            continue

        if side == "DR":
            dr_total += amt
        else:
            cr_total += amt

    dr_total = round(dr_total, 2)
    cr_total = round(cr_total, 2)
    balanced = round(dr_total - cr_total, 2) == 0.0

    if not balanced:
        errors.append(f"Not balanced: DR={dr_total} CR={cr_total}")

    if errors:
        raise ValueError("; ".join(errors))

    return {
        "ok": True,
        "dr_total": dr_total,
        "cr_total": cr_total,
        "balanced": balanced,
        "errors": []
    }
