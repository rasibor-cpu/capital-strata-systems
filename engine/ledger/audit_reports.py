from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional

from engine.ledger.ledger_store import LedgerStore
from engine.ledger.ledger_models import LedgerEntry, LedgerTransaction


class AuditReportEngine:
    """
    Audit & compliance reporting engine (v1).

    Produces:
    - Trade tickets (per execution)
    - End-of-day transaction listings
    - Aggregations for settlement and audit
    """

    def __init__(self, store: LedgerStore):
        self.store = store

    # ─────────────────────────────
    # Trade Ticket
    # ─────────────────────────────
    def trade_ticket(self, ledger_txn_id: str) -> str:
        """
        Returns a printable trade ticket for one LedgerTransaction.
        """
        txn: Optional[LedgerTransaction] = self.store.get_transaction(ledger_txn_id)
        if not txn:
            raise ValueError(f"LedgerTransaction not found: {ledger_txn_id}")

        lines: List[str] = []
        lines.append("=" * 80)
        lines.append("TRADE TICKET")
        lines.append("=" * 80)
        lines.append(f"Ledger Txn ID : {txn.ledger_txn_id}")
        lines.append(f"Execution ID  : {txn.execution_id}")
        lines.append(f"Order ID      : {txn.order_id}")
        lines.append(f"Txn Type      : {txn.txn_type}")
        lines.append(f"Created At    : {txn.created_at.isoformat()}")
        lines.append("-" * 80)

        for e in txn.entries:
            lines.append(
                f"{e.account_id:80}"
            )
            lines.append(
                f"  DR {e.debit} | CR {e.credit} | {e.currency} | {e.value_date.date()}"
            )
            if e.counterparty_id:
                lines.append(f"  Counterparty : {e.counterparty_id}")
            if e.settlement_account:
                lines.append(f"  Settlement A/C : {e.settlement_account}")
            if e.memo:
                lines.append(f"  Memo : {e.memo}")
            lines.append("-" * 80)

        lines.append("END OF TICKET")
        lines.append("=" * 80)
        return "\n".join(lines)

    # ─────────────────────────────
    # End-of-Day Report
    # ─────────────────────────────
    def end_of_day_report(
        self,
        business_date: date,
        *,
        company_id: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> str:
        """
        Printable end-of-day transaction listing.
        """
        lines: List[str] = []
        lines.append("=" * 100)
        lines.append(f"END OF DAY AUDIT REPORT — {business_date.isoformat()}")
        lines.append("=" * 100)

        for txn in self.store.transactions.values():
            if txn.created_at.date() != business_date:
                continue

            lines.append(
                f"{txn.created_at.isoformat()} | {txn.ledger_txn_id} | {txn.txn_type} | Exec={txn.execution_id}"
            )

            for e in txn.entries:
                if company_id and e.company_id != company_id:
                    continue
                if branch_id and e.branch_id != branch_id:
                    continue

                lines.append(
                    f"   {e.account_id} | DR={e.debit} CR={e.credit} {e.currency}"
                )

        lines.append("=" * 100)
        lines.append("END OF REPORT")
        return "\n".join(lines)

    # ─────────────────────────────
    # Settlement Aggregation
    # ─────────────────────────────
    def settlement_summary(
        self,
        *,
        counterparty_id: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Decimal]:
        """
        Aggregate net settlement amounts by counterparty and currency.
        """
        summary: Dict[str, Decimal] = {}

        for acct_id, entries in self.store.entries_by_account.items():
            for e in entries:
                if counterparty_id and e.counterparty_id != counterparty_id:
                    continue
                if currency and e.currency != currency:
                    continue

                key = f"{e.counterparty_id or 'UNKNOWN'}|{e.currency}"
                net = e.debit - e.credit
                summary[key] = summary.get(key, Decimal("0")) + net

        return summary