"""
Capital Strata Systems (CSS)
Phase 27A – Posting Governance Gate (Canonical Enforcement)

Governance Rules:
1. Only canonical customer accounts allowed (CUST-840-*)
2. Fail-closed model
3. Structured rejection response
"""

from __future__ import annotations

from typing import Dict


CANONICAL_CUSTOMER_PREFIX = "CUST-840-"


def validate_posting(posting: Dict) -> Dict:
    """
    Validates a single posting before it is committed.

    Returns:
        {
            status: "APPROVED" | "REJECTED",
            reason_code: str,
            message: str
        }
    """

    account_no = str(posting.get("account_no", "")).strip().upper()

    if not account_no:
        return {
            "status": "REJECTED",
            "reason_code": "MISSING_ACCOUNT",
            "message": "Posting rejected: account number is required."
        }

    # ---------------------------------------------------------
    # Canonical Customer Account Enforcement
    # ---------------------------------------------------------
    if account_no.startswith("CUST-"):
        if not account_no.startswith(CANONICAL_CUSTOMER_PREFIX):
            return {
                "status": "REJECTED",
                "reason_code": "INVALID_CUSTOMER_ACCOUNT_FORMAT",
                "message": (
                    f"Customer account '{account_no}' is not canonical. "
                    f"Valid customer accounts must start with '{CANONICAL_CUSTOMER_PREFIX}'."
                )
            }

    # ---------------------------------------------------------
    # Basic Debit/Credit Validation
    # ---------------------------------------------------------
    side = str(posting.get("side", "")).upper().strip()
    if side not in {"DR", "CR"}:
        return {
            "status": "REJECTED",
            "reason_code": "INVALID_SIDE",
            "message": "Posting rejected: side must be DR or CR."
        }

    try:
        amount = float(posting.get("amount", 0))
    except Exception:
        return {
            "status": "REJECTED",
            "reason_code": "INVALID_AMOUNT",
            "message": "Posting rejected: amount must be numeric."
        }

    if amount <= 0:
        return {
            "status": "REJECTED",
            "reason_code": "NON_POSITIVE_AMOUNT",
            "message": "Posting rejected: amount must be greater than zero."
        }

    # ---------------------------------------------------------
    # Approved
    # ---------------------------------------------------------
    return {
        "status": "APPROVED",
        "reason_code": "VALID",
        "message": "Posting approved."
    }