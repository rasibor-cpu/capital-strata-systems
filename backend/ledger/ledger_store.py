"""
ledger_store.py
Capital Strata Systems (CSS)

In-Memory Ledger Store
----------------------

This module is intentionally persistence-agnostic.
It can later be replaced by a database-backed store
without modifying LedgerEngine logic.

Responsibilities:
- Maintain account balances
- Maintain transaction history per account
- Provide safe mutation interface
- Provide read-only retrieval functions
"""

from __future__ import annotations
from decimal import Decimal
from typing import Dict, List
from datetime import datetime


class LedgerEntry:
    """
    Immutable ledger transaction entry.
    """

    def __init__(
        self,
        account_id: str,
        transaction_id: str,
        transaction_date: datetime,
        value_date: datetime,
        debit: Decimal,
        credit: Decimal,
        description: str,
        currency: str,
        balance_after: Decimal,
    ):
        self.account_id = account_id
        self.transaction_id = transaction_id
        self.transaction_date = transaction_date
        self.value_date = value_date
        self.debit = debit
        self.credit = credit
        self.description = description
        self.currency = currency
        self.balance_after = balance_after

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "transaction_id": self.transaction_id,
            "transaction_date": self.transaction_date.isoformat(),
            "value_date": self.value_date.isoformat(),
            "debit": str(self.debit),
            "credit": str(self.credit),
            "description": self.description,
            "currency": self.currency,
            "balance_after": str(self.balance_after),
        }


class LedgerStore:
    """
    In-memory ledger store.

    Internal structure:
        balances: Dict[str, Decimal]
        entries: Dict[str, List[LedgerEntry]]
    """

    def __init__(self):
        self._balances: Dict[str, Decimal] = {}
        self._entries: Dict[str, List[LedgerEntry]] = {}

    # =========================
    # ACCOUNT MANAGEMENT
    # =========================

    def ensure_account(self, account_id: str):
        if account_id not in self._balances:
            self._balances[account_id] = Decimal("0.00")
            self._entries[account_id] = []

    def get_balance(self, account_id: str) -> Decimal:
        self.ensure_account(account_id)
        return self._balances[account_id]

    def get_entries(self, account_id: str) -> List[LedgerEntry]:
        self.ensure_account(account_id)
        return list(self._entries[account_id])

    # =========================
    # MUTATION (CALLED ONLY BY LEDGER ENGINE)
    # =========================

    def apply_posting(
        self,
        account_id: str,
        transaction_id: str,
        transaction_date: datetime,
        value_date: datetime,
        debit: Decimal,
        credit: Decimal,
        description: str,
        currency: str,
    ) -> LedgerEntry:
        """
        Applies a posting to an account.
        Debit increases balance.
        Credit decreases balance.
        """

        self.ensure_account(account_id)

        current_balance = self._balances[account_id]
        new_balance = current_balance + debit - credit

        entry = LedgerEntry(
            account_id=account_id,
            transaction_id=transaction_id,
            transaction_date=transaction_date,
            value_date=value_date,
            debit=debit,
            credit=credit,
            description=description,
            currency=currency,
            balance_after=new_balance,
        )

        self._balances[account_id] = new_balance
        self._entries[account_id].append(entry)

        return entry

    # =========================
    # SYSTEM WIDE VIEWS
    # =========================

    def all_balances(self) -> Dict[str, Decimal]:
        return dict(self._balances)

    def all_entries(self) -> Dict[str, List[LedgerEntry]]:
        return {k: list(v) for k, v in self._entries.items()}