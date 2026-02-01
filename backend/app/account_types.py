"""
Account Types Catalog (Dropdown Source)

This defines the canonical list of account type codes used when
creating sub-accounts under a customer's base account number.

Rules:
- code is stable, uppercase, short
- label is user-friendly
- category helps reporting/limits later
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass(frozen=True)
class AccountType:
    code: str
    label: str
    category: str


ACCOUNT_TYPES: List[AccountType] = [
    AccountType("CUR", "Current Account", "deposit"),
    AccountType("SAV", "Savings Account", "deposit"),
    AccountType("FD", "Fixed Deposit", "term"),
    AccountType("BA", "Banker’s Acceptance (BA)", "market"),
    AccountType("CP", "Commercial Paper (CP)", "market"),
    AccountType("FCY", "Foreign Currency Account", "deposit"),
    AccountType("PTA", "Personal Travel Allowance (PTA)", "fx"),
    AccountType("CARD", "Card Account", "card"),
]

ACCOUNT_TYPE_INDEX: Dict[str, AccountType] = {a.code: a for a in ACCOUNT_TYPES}


def list_account_types() -> List[dict]:
    """Convenience for UI dropdowns."""
    return [{"code": a.code, "label": a.label, "category": a.category} for a in ACCOUNT_TYPES]


def is_valid_account_type(code: str) -> bool:
    return code in ACCOUNT_TYPE_INDEX
