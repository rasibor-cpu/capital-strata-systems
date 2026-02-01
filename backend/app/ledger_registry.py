# backend/app/ledger_registry.py
# Authoritative Ledger Registry
# Balances are DERIVED from immutable journal entries only

from datetime import datetime
from collections import defaultdict
from typing import Dict, List

# In-memory immutable journal store (later DB-backed)
_JOURNAL: List[dict] = []

# Cached balances (derived, never manually edited)
_BALANCE_CACHE: Dict[str, float] = defaultdict(float)


def _sub_account_id(base_account_no: str, account_type_code: str, currency: str) -> str:
    return f"{base_account_no}-{account_type_code}-{currency}"


def post_journal_entry(
    *,
    ticket_id: str,
    user_id: str,
    side: str,  # "DR" or "CR"
    base_account_no: str,
    account_type_code: str,
    currency: str,
    amount: float,
    narrative: str,
) -> dict:
    """
    Append an immutable journal entry and derive new balance.
    """

    if side not in ("DR", "CR"):
        raise ValueError("Invalid journal side")

    if amount <= 0:
        raise ValueError("Journal amount must be positive")

    sub_account = _sub_account_id(base_account_no, account_type_code, currency)

    delta = amount if side == "DR" else -amount

    journal_id = f"J-{len(_JOURNAL) + 1:06d}"

    entry = {
        "journal_id": journal_id,
        "ticket_id": ticket_id,
        "user_id": user_id,
        "posted_at": datetime.utcnow().isoformat(),
        "side": side,
        "base_account_no": base_account_no,
        "account_type_code": account_type_code,
        "currency": currency,
        "sub_account_id": sub_account,
        "delta": delta,
        "narrative": narrative,
    }

    _JOURNAL.append(entry)

    # Derive balance strictly via journal delta
    _BALANCE_CACHE[sub_account] += delta

    return {
        "journal_id": journal_id,
        "sub_account_id": sub_account,
        "delta": delta,
        "new_balance": _BALANCE_CACHE[sub_account],
    }


def get_sub_account_balance(
    base_account_no: str,
    account_type_code: str,
    currency: str,
) -> float:
    """
    Read-only derived balance.
    """
    sub_account = _sub_account_id(base_account_no, account_type_code, currency)
    return _BALANCE_CACHE.get(sub_account, 0.0)


def get_all_balances_for_customer(base_account_no: str) -> Dict[str, float]:
    """
    Returns all sub-account balances for a customer.
    """
    return {
        k: v
        for k, v in _BALANCE_CACHE.items()
        if k.startswith(f"{base_account_no}-")
    }


def get_full_journal() -> List[dict]:
    """
    Immutable journal view.
    """
    return list(_JOURNAL)
