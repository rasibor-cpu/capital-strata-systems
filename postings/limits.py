"""
postings/limits.py
------------------
Limits and approval thresholds for posting workflow.

Scope:
- Determine required approval level based on amount thresholds
- Optional daily caps (maker + customer) – logic only (no persistence yet)

This module is UI-agnostic and can be called by maker/checker flows.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict
from datetime import date

from posting_ledger import APPROVAL_ORDER


# Approval levels (match posting_ledger.APPROVAL_ORDER keys)
LEVEL_AUTO = "AUTO"
LEVEL_USER = "USER"
LEVEL_SUPERVISOR = "SUPERVISOR"
LEVEL_MANAGER = "MANAGER"
LEVEL_ADMIN = "ADMIN"
LEVEL_SUPER = "SUPER"


@dataclass(frozen=True)
class ThresholdBands:
    """
    Amount thresholds in base currency (or transaction currency if you choose).
    Values are inclusive upper bounds for each band.
    """
    auto_max: Decimal = Decimal("2000000")     # 0 - 2,000,000
    user_max: Decimal = Decimal("15000000")    # 2,000,001 - 15,000,000
    supervisor_max: Decimal = Decimal("50000000")  # 15,000,001 - 50,000,000
    admin_max: Decimal = Decimal("200000000")  # 50,000,001 - 200,000,000
    # Above admin_max => SUPER


def required_approval_level_for_amount(amount: Decimal, bands: ThresholdBands) -> str:
    if amount <= Decimal("0"):
        raise ValueError("amount must be > 0")

    if amount <= bands.auto_max:
        return LEVEL_AUTO
    if amount <= bands.user_max:
        return LEVEL_USER
    if amount <= bands.supervisor_max:
        return LEVEL_SUPERVISOR
    if amount <= bands.admin_max:
        return LEVEL_ADMIN
    return LEVEL_SUPER


@dataclass
class DailyCounter:
    """
    Minimal in-memory daily counters for caps.
    Replace with persistence later.
    """
    by_maker: Dict[str, Decimal]
    by_customer: Dict[str, Decimal]
    day: str  # YYYY-MM-DD

    @classmethod
    def for_today(cls) -> "DailyCounter":
        return cls(by_maker={}, by_customer={}, day=date.today().isoformat())

    def _ensure_day(self) -> None:
        today = date.today().isoformat()
        if self.day != today:
            self.by_maker = {}
            self.by_customer = {}
            self.day = today

    def add(self, *, maker_user: str, customer_id: str, amount: Decimal) -> None:
        self._ensure_day()
        if amount <= Decimal("0"):
            raise ValueError("amount must be > 0")
        mu = (maker_user or "").strip()
        cid = (customer_id or "").strip()
        if not mu:
            raise ValueError("maker_user required")
        if not cid:
            raise ValueError("customer_id required")

        self.by_maker[mu] = self.by_maker.get(mu, Decimal("0")) + amount
        self.by_customer[cid] = self.by_customer.get(cid, Decimal("0")) + amount

    def get_maker_total(self, maker_user: str) -> Decimal:
        self._ensure_day()
        return self.by_maker.get((maker_user or "").strip(), Decimal("0"))

    def get_customer_total(self, customer_id: str) -> Decimal:
        self._ensure_day()
        return self.by_customer.get((customer_id or "").strip(), Decimal("0"))


def enforce_daily_caps(
    *,
    counters: DailyCounter,
    maker_user: str,
    customer_id: str,
    amount: Decimal,
    maker_daily_cap: Optional[Decimal] = None,
    customer_daily_cap: Optional[Decimal] = None,
) -> None:
    """
    Raises ValueError if caps would be breached. If ok, does NOT mutate counters.
    Caller should counters.add(...) after successful posting/approval.
    """
    if amount <= Decimal("0"):
        raise ValueError("amount must be > 0")

    current_maker = counters.get_maker_total(maker_user)
    current_customer = counters.get_customer_total(customer_id)

    if maker_daily_cap is not None and (current_maker + amount) > maker_daily_cap:
        raise ValueError("maker daily cap exceeded")

    if customer_daily_cap is not None and (current_customer + amount) > customer_daily_cap:
        raise ValueError("customer daily cap exceeded")


def is_level_sufficient(required: str, got: str) -> bool:
    """
    Compare approval levels using APPROVAL_ORDER.
    """
    r = APPROVAL_ORDER.get((required or "").upper())
    g = APPROVAL_ORDER.get((got or "").upper())
    if r is None or g is None:
        return False
    return g >= r
