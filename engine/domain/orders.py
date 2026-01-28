from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict


@dataclass
class OrderIntent:
    """
    Declarative order request emitted by strategy.
    Contains NO execution, pricing, or fee logic.
    """

    # Identity
    order_id: str
    user_id: str

    # Entity scope (for reporting / audit / aggregation)
    company_id: Optional[str] = None
    branch_id: Optional[str] = None
    department_id: Optional[str] = None

    # Instrument
    symbol: str = ""
    side: str = ""          # BUY / SELL
    quantity: float = 0.0
    order_type: str = ""    # MARKET / LIMIT
    limit_price: Optional[float] = None
    currency: str = "USD"

    # Dates
    order_date: Optional[datetime] = None
    requested_exec_date: Optional[datetime] = None  # forward orders

    # Session / regime labels (labels only)
    session_id: Optional[str] = None
    regime_tag: Optional[str] = None

    # Counterparty (may be populated at order or later)
    counterparty_id: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None

    # Free-form metadata (never interpreted by execution)
    meta: Optional[Dict] = None