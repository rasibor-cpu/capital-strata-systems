"""
General Ledger Engine – Phase 14
Capital Strata Systems

Maintains running balances per account.
Real-time update on journal append.
"""

from decimal import Decimal
from typing import Dict
from .journal import JournalEntry


class GeneralLedger:

    def __init__(self):
        self._balances: Dict[str, Decimal] = {}

    def apply(self, entry: JournalEntry):

        current = self._balances.get(entry.account_no, Decimal("0"))

        if entry.side == "DR":
            current += entry.amount
        elif entry.side == "CR":
            current -= entry.amount
        else:
            raise ValueError("Invalid side. Must be DR or CR.")

        self._balances[entry.account_no] = current

    def balance(self, account_no: str) -> Decimal:
        return self._balances.get(account_no, Decimal("0"))

    def trial_balance(self) -> Dict[str, Decimal]:
        return dict(self._balances)