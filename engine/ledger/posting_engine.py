from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

from engine.domain.executions import ExecutionReport
from engine.ledger.ledger_models import LedgerTransaction, LedgerEntry
from engine.ledger.ledger_store import LedgerStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PostingEngine:
    """
    Converts ExecutionReport into balanced double-entry postings.

    Currency policy (v1):
    - Post in settlement currency when provided, else execution currency.
    - No FX translation in v1 (handled in a later FX module).
    """

    def __init__(self, store: LedgerStore):
        self.store = store

    def post_execution(self, r: ExecutionReport) -> LedgerTransaction:
        """
        Creates and stores a balanced LedgerTransaction for one ExecutionReport.
        """
        posting_ccy = (r.settlement_currency or r.currency) or "NA"
        value_date = r.execution_date or _utc_now()

        gross = Decimal(str(r.gross_amount or 0.0))
        comm = Decimal(str(r.brokerage_commission or 0.0))
        tax = Decimal(str(r.tax_amount or 0.0))
        net = Decimal(str(r.net_amount or 0.0))

        # Account IDs (scoped + currency)
        cash_acct = self._acct_id("CASH", posting_ccy, r)
        pos_acct = self._acct_id(f"POSITION:{r.symbol}", posting_ccy, r)
        fee_acct = self._acct_id("EXPENSE:BROKERAGE", posting_ccy, r)
        tax_acct = self._acct_id("EXPENSE:TAX", posting_ccy, r)

        txn = LedgerTransaction(
            txn_type="EXECUTION",
            created_at=_utc_now(),
            execution_id=r.execution_id,
            order_id=r.order_id,
        )

        side = (r.side or "").upper()

        if side == "BUY":
            txn.entries.append(self._debit(pos_acct, gross, posting_ccy, value_date, r, memo=f"Buy {r.symbol}"))
            if comm > 0:
                txn.entries.append(self._debit(fee_acct, comm, posting_ccy, value_date, r, memo="Brokerage commission"))
            if tax > 0:
                txn.entries.append(self._debit(tax_acct, tax, posting_ccy, value_date, r, memo="Transaction tax"))
            txn.entries.append(self._credit(cash_acct, net, posting_ccy, value_date, r, memo="Cash settlement (buy)"))

        elif side == "SELL":
            txn.entries.append(self._debit(cash_acct, net, posting_ccy, value_date, r, memo=f"Cash settlement (sell {r.symbol})"))
            txn.entries.append(self._credit(pos_acct, gross, posting_ccy, value_date, r, memo=f"Sell {r.symbol}"))
            if comm > 0:
                txn.entries.append(self._debit(fee_acct, comm, posting_ccy, value_date, r, memo="Brokerage commission"))
            if tax > 0:
                txn.entries.append(self._debit(tax_acct, tax, posting_ccy, value_date, r, memo="Transaction tax"))
        else:
            raise ValueError(f"Cannot post execution with invalid side: {r.side}")

        self._assert_balanced(txn)
        self.store.add_transaction(txn)
        return txn

    # ─────────────────────────────
    # Helpers
    # ─────────────────────────────
    def _acct_id(self, base: str, currency: str, r: ExecutionReport) -> str:
        """
        Produces a scoped account id for aggregation:
        company/branch/department/user + base + currency
        """
        parts = [
            r.company_id or "COMPANY:NA",
            r.branch_id or "BRANCH:NA",
            r.department_id or "DEPT:NA",
            r.user_id or "USER:NA",
            base,
            currency,
        ]
        return "|".join(parts)

    def _debit(
        self,
        account_id: str,
        amount: Decimal,
        currency: str,
        value_date: datetime,
        r: ExecutionReport,
        memo: Optional[str] = None,
    ) -> LedgerEntry:
        return LedgerEntry(
            ledger_txn_id="",
            account_id=account_id,
            debit=amount,
            credit=Decimal("0.00"),
            currency=currency,
            value_date=value_date,
            execution_id=r.execution_id,
            order_id=r.order_id,
            company_id=r.company_id,
            branch_id=r.branch_id,
            department_id=r.department_id,
            user_id=r.user_id,
            counterparty_id=r.counterparty_id,
            settlement_account=r.settlement_account_number,
            memo=memo,
            meta={"symbol": r.symbol, "side": r.side},
        )

    def _credit(
        self,
        account_id: str,
        amount: Decimal,
        currency: str,
        value_date: datetime,
        r: ExecutionReport,
        memo: Optional[str] = None,
    ) -> LedgerEntry:
        return LedgerEntry(
            ledger_txn_id="",
            account_id=account_id,
            debit=Decimal("0.00"),
            credit=amount,
            currency=currency,
            value_date=value_date,
            execution_id=r.execution_id,
            order_id=r.order_id,
            company_id=r.company_id,
            branch_id=r.branch_id,
            department_id=r.department_id,
            user_id=r.user_id,
            counterparty_id=r.counterparty_id,
            settlement_account=r.settlement_account_number,
            memo=memo,
            meta={"symbol": r.symbol, "side": r.side},
        )

    def _assert_balanced(self, txn: LedgerTransaction) -> None:
        total_debit = sum((e.debit for e in txn.entries), Decimal("0.00"))
        total_credit = sum((e.credit for e in txn.entries), Decimal("0.00"))
        if total_debit != total_credit:
            raise ValueError(f"LedgerTransaction not balanced: debit={total_debit} credit={total_credit}")
