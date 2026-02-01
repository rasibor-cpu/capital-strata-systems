"""
Account Registry (Phase 14 foundation)

Purpose:
- Support ONE base customer account number that can hold multiple sub-accounts:
    (base_account_no + account_type_code + currency) -> sub-account

- Maintain running balances per sub-account.
- Provide deterministic lookup/creation for postings.

Key concept:
- base_account_no: customer identifier (common across all products)
- account_type_code: dropdown-selected product code (CUR/SAV/FD/BA/CP/FCY/PTA/CARD)
- currency: full-text uppercase currency name (e.g., "UNITED STATES DOLLAR")

Sub-account key:
  (base_account_no, account_type_code, currency)
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, Any
from datetime import datetime

from .account_types import is_valid_account_type


SubAccountKey = Tuple[str, str, str]  # (base_account_no, account_type_code, currency)


@dataclass
class SubAccount:
    base_account_no: str
    account_type_code: str
    currency: str
    balance: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def sub_account_id(self) -> str:
        # Deterministic ID (human readable)
        return f"{self.base_account_no}-{self.account_type_code}-{self.currency}"


# In-memory registry (Phase 14: can be swapped for DB)
_SUB_ACCOUNTS: Dict[SubAccountKey, SubAccount] = {}


def normalize_currency(currency: str) -> str:
    c = (currency or "").strip()
    return c.upper()


def normalize_base_account_no(base_account_no: str) -> str:
    return (base_account_no or "").strip()


def normalize_account_type_code(account_type_code: str) -> str:
    return (account_type_code or "").strip().upper()


def get_or_create_sub_account(
    base_account_no: str,
    account_type_code: str,
    currency: str,
    *,
    create_meta: Optional[Dict[str, Any]] = None
) -> SubAccount:
    base = normalize_base_account_no(base_account_no)
    code = normalize_account_type_code(account_type_code)
    ccy = normalize_currency(currency)

    if not base:
        raise ValueError("base_account_no is required")
    if not is_valid_account_type(code):
        raise ValueError(f"Invalid account_type_code: {code}")
    if not ccy or ccy.upper() != ccy:
        raise ValueError("currency must be full-text uppercase")

    key: SubAccountKey = (base, code, ccy)

    if key in _SUB_ACCOUNTS:
        return _SUB_ACCOUNTS[key]

    sa = SubAccount(
        base_account_no=base,
        account_type_code=code,
        currency=ccy,
        balance=0.0,
        meta=create_meta or {},
    )
    _SUB_ACCOUNTS[key] = sa
    return sa


def get_sub_account(base_account_no: str, account_type_code: str, currency: str) -> Optional[SubAccount]:
    base = normalize_base_account_no(base_account_no)
    code = normalize_account_type_code(account_type_code)
    ccy = normalize_currency(currency)
    return _SUB_ACCOUNTS.get((base, code, ccy))


def apply_delta(
    base_account_no: str,
    account_type_code: str,
    currency: str,
    delta: float,
    *,
    meta: Optional[Dict[str, Any]] = None
) -> SubAccount:
    """
    Apply a signed delta to the sub-account balance.
    Positive delta increases balance; negative delta reduces it.
    Returns updated SubAccount (latest balance is authoritative).
    """
    sa = get_or_create_sub_account(base_account_no, account_type_code, currency)
    sa.balance = float(sa.balance) + float(delta)

    if meta:
        sa.meta.setdefault("updates", []).append(
            {"at": datetime.utcnow().isoformat(), "delta": float(delta), "meta": meta}
        )

    return sa


def snapshot() -> Dict[str, Any]:
    """For diagnostics / reporting."""
    out: Dict[str, Any] = {}
    for key, sa in _SUB_ACCOUNTS.items():
        out[sa.sub_account_id] = {
            "base_account_no": sa.base_account_no,
            "account_type_code": sa.account_type_code,
            "currency": sa.currency,
            "balance": sa.balance,
            "created_at": sa.created_at,
        }
    return out
