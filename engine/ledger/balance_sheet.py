from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple

from engine.ledger.ledger_models import BalanceSheetSnapshot
from engine.ledger.ledger_store import LedgerStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AccountTotals:
    assets: Decimal = Decimal("0")
    liabilities: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")


class BalanceSheetEngine:
    """
    Balance Sheet engine (v1).

    - Aggregates ledger entries by account class
    - Computes balance sheet per currency
    - No FX translation yet (home currency handled later)
    """

    def __init__(self, store: LedgerStore):
        self.store = store

    # ─────────────────────────────
    # Public API
    # ─────────────────────────────
    def snapshot(
        self,
        *,
        as_of: Optional[datetime] = None,
        company_id: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> None:
        """
        Create balance sheet snapshots per currency.

        Assets = Debits - Credits
        Liabilities/Equity = Credits - Debits
        """
        as_of = as_of or _utc_now()

        totals_by_currency: Dict[str, AccountTotals] = {}

        for acct_id, entries in self.store.entries_by_account.items():
            parts = acct_id.split("|")
            if len(parts) < 6:
                continue

            comp, br, dept, usr, base, currency = parts

            if company_id is not None and comp != (company_id or "COMPANY:NA"):
                continue
            if branch_id is not None and br != (branch_id or "BRANCH:NA"):
                continue

            if currency not in totals_by_currency:
                totals_by_currency[currency] = AccountTotals()

            totals = totals_by_currency[currency]

            for e in entries:
                net = e.debit - e.credit

                if base.startswith(("CASH", "POSITION", "ASSET")):
                    totals.assets += net
                elif base.startswith(("LIABILITY",)):
                    totals.liabilities -= net
                elif base.startswith(("EQUITY", "EXPENSE", "INCOME")):
                    totals.equity -= net

        # Persist snapshots
        for ccy, t in totals_by_currency.items():
            snap = BalanceSheetSnapshot(
                as_of=as_of,
                currency=ccy,
                assets=t.assets,
                liabilities=t.liabilities,
                equity=t.equity,
                company_id=company_id,
                branch_id=branch_id,
                meta={
                    "balanced": str(t.assets == (t.liabilities + t.equity)),
                },
            )
            self.store.add_balance_sheet(snap)
