from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal
import uuid


# =============================
# CORE LEDGER ENTITIES
# =============================

@dataclass
class LedgerAccount:
    """
    Chart-of-Accounts entry.
    """
    account_id: str
    account_name: str
    account_type: str  # ASSET / LIABILITY / EQUITY / INCOME / EXPENSE
    currency: str

    company_id: Optional[str] = None
    branch_id: Optional[str] = None
    department_id: Optional[str] = None
    user_id: Optional[str] = None

    is_control_account: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LedgerEntry:
    """
    Atomic double-entry posting line.
    Debit OR Credit — never both.
    """
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ledger_txn_id: str = ""
    account_id: str = ""

    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")

    currency: str = ""
    value_date: datetime = field(default_factory=datetime.utcnow)

    # Linkage
    execution_id: Optional[str] = None
    order_id: Optional[str] = None

    # Org dimensions
    company_id: Optional[str] = None
    branch_id: Optional[str] = None
    department_id: Optional[str] = None
    user_id: Optional[str] = None

    # Settlement / counterparty context
    counterparty_id: Optional[str] = None
    settlement_account: Optional[str] = None

    memo: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LedgerTransaction:
    """
    Groups multiple LedgerEntry lines.
    Must balance to zero.
    """
    ledger_txn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    txn_type: str = ""  # EXECUTION / FEE / TAX / SETTLEMENT / ADJUSTMENT
    created_at: datetime = field(default_factory=datetime.utcnow)

    execution_id: Optional[str] = None
    order_id: Optional[str] = None

    entries: list[LedgerEntry] = field(default_factory=list)

    meta: Dict[str, Any] = field(default_factory=dict)


# =============================
# POSITIONS & PNL
# =============================

@dataclass
class PositionLot:
    """
    Lot-level position tracking (FIFO / avg cost v1).
    """
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    currency: str

    opened_at: datetime = field(default_factory=datetime.utcnow)
    execution_id: Optional[str] = None
    order_id: Optional[str] = None


@dataclass
class PnLSnapshot:
    """
    Rolling P&L snapshot.
    """
    as_of: datetime
    symbol: str
    currency: str

    realized_pnl: Decimal = Decimal("0.00")
    unrealized_pnl: Decimal = Decimal("0.00")

    company_id: Optional[str] = None
    branch_id: Optional[str] = None
    department_id: Optional[str] = None
    user_id: Optional[str] = None

    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BalanceSheetSnapshot:
    """
    Balance sheet as of a point in time.
    """
    as_of: datetime
    currency: str

    total_assets: Decimal = Decimal("0.00")
    total_liabilities: Decimal = Decimal("0.00")
    total_equity: Decimal = Decimal("0.00")

    company_id: Optional[str] = None
    branch_id: Optional[str] = None

    meta: Dict[str, Any] = field(default_factory=dict)