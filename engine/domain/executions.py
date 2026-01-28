from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict


@dataclass
class ExecutionReport:
    """
    Authoritative record of what actually happened.
    This is the legal / audit / settlement source of truth.
    """

    # ─────────────────────────────
    # Identity & scope
    # ─────────────────────────────
    order_id: str
    execution_id: str

    user_id: str
    company_id: Optional[str]
    branch_id: Optional[str]
    department_id: Optional[str]

    # ─────────────────────────────
    # Instrument
    # ─────────────────────────────
    symbol: str
    side: str                # BUY / SELL
    currency: str

    # ─────────────────────────────
    # Dates
    # ─────────────────────────────
    order_date: datetime
    requested_exec_date: Optional[datetime]
    execution_date: datetime
    settlement_date: Optional[datetime]

    # ─────────────────────────────
    # Quantities & pricing
    # ─────────────────────────────
    filled_qty: float
    fill_price: float
    avg_price: float
    gross_amount: float

    # ─────────────────────────────
    # Fees & taxes
    # ─────────────────────────────
    commission_rate_pct: float
    brokerage_commission: float
    tax_rate_pct: float
    tax_amount: float
    total_fees_and_taxes: float
    net_amount: float

    # ─────────────────────────────
    # Counterparty
    # ─────────────────────────────
    counterparty_id: Optional[str]
    counterparty_name: Optional[str]
    counterparty_account: Optional[str]

    # ─────────────────────────────
    # Financial institution & settlement
    # ─────────────────────────────
    fi_id: Optional[str]
    fi_name: Optional[str]
    fi_branch_id: Optional[str]
    fi_branch_name: Optional[str]

    settlement_account_name: Optional[str]
    settlement_account_number: Optional[str]
    settlement_sort_code: Optional[str]
    settlement_routing_code: Optional[str]
    settlement_swift_bic: Optional[str]
    settlement_iban: Optional[str]
    settlement_currency: Optional[str]
    settlement_reference: Optional[str]

    # ─────────────────────────────
    # Governance / execution metadata
    # ─────────────────────────────
    fee_schedule_id: str
    fee_schedule_version: str

    broker_name: str
    is_paper: bool

    latency_ms: Optional[int]
    slippage_bps: Optional[float]
    slippage_amount: Optional[float]

    status: str              # FILLED / PARTIAL / REJECTED
    seed: Optional[str]

    meta: Optional[Dict]