"""
ledger_engine.py
Capital Strata Systems (CSS)

Ledger Engine
-------------

Institutional double-entry enforcement layer.

Key Guarantees:
- Single ledger universe
- Real-time balance mutation
- Atomic multi-line journal posting
- Idempotency: BLOCK only when SAME transaction_id is reused on SAME transaction date
"""

from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from typing import List, Dict

from .ledger_store import LedgerStore


class PostingLine:
    """
    Represents one line of a journal entry.
    Exactly one of debit or credit must be > 0.
    """

    def __init__(
        self,
        account_id: str,
        debit: Decimal = Decimal("0.00"),
        credit: Decimal = Decimal("0.00"),
    ):
        if debit > 0 and credit > 0:
            raise ValueError("A line cannot have both debit and credit.")
        if debit == 0 and credit == 0:
            raise ValueError("A line must contain either debit or credit.")
        if debit < 0 or credit < 0:
            raise ValueError("Debit and credit cannot be negative.")

        self.account_id = account_id
        self.debit = debit
        self.credit = credit


class LedgerEngine:
    """
    Central accounting enforcement engine.
    """

    def __init__(self, store: LedgerStore):
        self.store = store

    def post_journal(
        self,
        transaction_id: str,
        transaction_date: datetime,
        value_date: datetime,
        currency: str,
        description: str,
        lines: List[PostingLine],
    ) -> Dict[str, Decimal]:
        if not lines or len(lines) < 2:
            raise ValueError("Journal must contain at least two lines.")

        # Idempotency rule (your requirement):
        # Flag ONLY if same transaction_id is re-used on the same transaction date.
        if self.store.has_posted(transaction_id, transaction_date):
            dkey = self.store.txn_date_key(transaction_date)
            raise ValueError(f"Duplicate posting blocked: transaction_id={transaction_id} date={dkey}")

        total_debit = sum(line.debit for line in lines)
        total_credit = sum(line.credit for line in lines)

        if total_debit != total_credit:
            raise ValueError(
                f"Unbalanced journal: debit {total_debit} != credit {total_credit}"
            )

        # Stage balances first (atomic intent)
        staged_new_balances = {}
        for line in lines:
            current_balance = self.store.get_balance(line.account_id)
            staged_new_balances[line.account_id] = current_balance + line.debit - line.credit

        # Apply mutations (after all validations succeeded)
        updated_balances = {}
        for line in lines:
            entry = self.store.apply_posting(
                account_id=line.account_id,
                transaction_id=transaction_id,
                transaction_date=transaction_date,
                value_date=value_date,
                debit=line.debit,
                credit=line.credit,
                description=description,
                currency=currency,
            )
            updated_balances[line.account_id] = entry.balance_after

        # Register idempotency key only after successful apply
        self.store.register_posted(transaction_id, transaction_date)

        return updated_balances

    def get_balance(self, account_id: str) -> Decimal:
        return self.store.get_balance(account_id)

    def get_all_balances(self) -> Dict[str, Decimal]:
        return self.store.all_balances()