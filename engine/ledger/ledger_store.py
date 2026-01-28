from collections import defaultdict
from typing import Dict, List, Optional
from datetime import datetime

from engine.ledger.ledger_models import (
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    PositionLot,
    PnLSnapshot,
    BalanceSheetSnapshot,
)


class LedgerStore:
    """
    In-memory ledger store (v1).

    Acts as the system of record for:
    - chart of accounts
    - ledger transactions
    - ledger entries
    - positions
    - P&L snapshots
    - balance sheet snapshots

    Designed to be replaced by DB / event store later.
    """

    def __init__(self):
        # Chart of accounts
        self.accounts: Dict[str, LedgerAccount] = {}

        # Ledger
        self.transactions: Dict[str, LedgerTransaction] = {}
        self.entries_by_account: Dict[str, List[LedgerEntry]] = defaultdict(list)

        # Positions
        self.positions: Dict[str, List[PositionLot]] = defaultdict(list)  # key = symbol

        # P&L snapshots
        self.pnl_snapshots: List[PnLSnapshot] = []

        # Balance sheet snapshots
        self.balance_sheets: List[BalanceSheetSnapshot] = []

    # ─────────────────────────────
    # Accounts
    # ─────────────────────────────
    def add_account(self, account: LedgerAccount) -> None:
        self.accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Optional[LedgerAccount]:
        return self.accounts.get(account_id)

    # ─────────────────────────────
    # Ledger transactions & entries
    # ─────────────────────────────
    def add_transaction(self, txn: LedgerTransaction) -> None:
        self.transactions[txn.ledger_txn_id] = txn
        for entry in txn.entries:
            self.entries_by_account[entry.account_id].append(entry)

    def get_transaction(self, ledger_txn_id: str) -> Optional[LedgerTransaction]:
        return self.transactions.get(ledger_txn_id)

    def get_entries_for_account(self, account_id: str) -> List[LedgerEntry]:
        return self.entries_by_account.get(account_id, [])

    # ─────────────────────────────
    # Positions
    # ─────────────────────────────
    def add_position_lot(self, lot: PositionLot) -> None:
        self.positions[lot.symbol].append(lot)

    def get_positions(self, symbol: Optional[str] = None) -> Dict[str, List[PositionLot]]:
        if symbol:
            return {symbol: self.positions.get(symbol, [])}
        return dict(self.positions)

    # ─────────────────────────────
    # P&L
    # ─────────────────────────────
    def add_pnl_snapshot(self, snap: PnLSnapshot) -> None:
        self.pnl_snapshots.append(snap)

    def get_latest_pnl(
        self,
        *,
        company_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        department_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[PnLSnapshot]:
        """
        Return matching P&L snapshots, newest first.
        """
        results = [
            s
            for s in self.pnl_snapshots
            if (company_id is None or s.company_id == company_id)
            and (branch_id is None or s.branch_id == branch_id)
            and (department_id is None or s.department_id == department_id)
            and (user_id is None or s.user_id == user_id)
        ]
        return sorted(results, key=lambda x: x.as_of, reverse=True)

    # ─────────────────────────────
    # Balance Sheet
    # ─────────────────────────────
    def add_balance_sheet(self, snap: BalanceSheetSnapshot) -> None:
        self.balance_sheets.append(snap)

    def get_latest_balance_sheet(
        self,
        *,
        company_id: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> Optional[BalanceSheetSnapshot]:
        """
        Return most recent matching balance sheet snapshot.
        """
        candidates = [
            s
            for s in self.balance_sheets
            if (company_id is None or s.company_id == company_id)
            and (branch_id is None or s.branch_id == branch_id)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x.as_of)