"""
Account ID Standard – v1 (Governance-Locked)
Capital Strata Systems

Customer Account (10 digits):
  ABCD-EFG-HIJ  (display with dashes)
  ABCD = 4-digit branch/sort code
  EFG  = ISO-4217 numeric currency code (3 digits) e.g., USD=840, NGN=566
  HIJ  = 3-digit serial within branch+currency

Internal GL Account (10 digits):
  Same 10-digit format BUT MUST start with "000" (i.e., ABCD in 0000..0009)
  This flags "internal ledger" at a glance.

Canonical storage:
  10 digits only, no dashes/spaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AccountIdParts:
    branch_code: str   # ABCD (4)
    currency_code: str # EFG  (3) ISO numeric
    serial: str        # HIJ  (3)

    @property
    def canonical(self) -> str:
        return f"{self.branch_code}{self.currency_code}{self.serial}"

    @property
    def display(self) -> str:
        return f"{self.branch_code}-{self.currency_code}-{self.serial}"


def normalize_account_id(value: str) -> str:
    """
    Accepts:
      - '1234-840-001'
      - '1234840001'
      - ' 1234 840 001 '
    Returns canonical '1234840001'
    """
    if value is None:
        raise ValueError("Account ID is required")
    s = str(value).strip().replace("-", "").replace(" ", "")
    if not s.isdigit():
        raise ValueError(f"Account ID must be digits only after normalization. Got: {value!r}")
    return s


def parse_account_id(value: str) -> AccountIdParts:
    s = normalize_account_id(value)
    if len(s) != 10:
        raise ValueError(f"Account ID must be exactly 10 digits. Got {len(s)}: {s!r}")
    return AccountIdParts(branch_code=s[0:4], currency_code=s[4:7], serial=s[7:10])


def format_account_id(value: str) -> str:
    p = parse_account_id(value)
    return p.display


def is_internal_gl(value: str) -> bool:
    s = normalize_account_id(value)
    if len(s) != 10:
        return False
    return s.startswith("000")


def validate_customer_acct(value: str) -> str:
    """
    Customer accounts must NOT start with '000' (reserved for internal GL).
    Returns canonical.
    """
    s = normalize_account_id(value)
    if len(s) != 10:
        raise ValueError(f"Customer account must be 10 digits. Got {len(s)}: {s!r}")
    if s.startswith("000"):
        raise ValueError(f"Customer account cannot start with '000' (reserved for internal GL). Got: {s!r}")
    # currency_code must be 3 digits (ISO numeric) — already enforced by digits + length
    return s


def validate_internal_gl(value: str) -> str:
    """
    Internal GL must start with '000'.
    Returns canonical.
    """
    s = normalize_account_id(value)
    if len(s) != 10:
        raise ValueError(f"Internal GL account must be 10 digits. Got {len(s)}: {s!r}")
    if not s.startswith("000"):
        raise ValueError(f"Internal GL account must start with '000'. Got: {s!r}")
    return s


def try_normalize_10digits(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().replace("-", "").replace(" ", "")
    if s.isdigit() and len(s) == 10:
        return s
    return None