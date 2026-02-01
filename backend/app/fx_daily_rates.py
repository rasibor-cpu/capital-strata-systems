"""
Daily FX Rates (Treasury Control)

Rules:
- ONE base currency (e.g. NGN) is the anchor.
- Treasury/Admin defines USD rate vs base currency daily.
- All other currencies are derived from USD.
- Rates are locked per business day once set.
- Source can be MANUAL or AUTOMATED (Reuters/Bloomberg/etc).
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import date, datetime


# -----------------------------
# Configuration
# -----------------------------

BASE_CURRENCY = "NIGERIAN NAIRA"   # Changeable only by system config
ANCHOR_CURRENCY = "UNITED STATES DOLLAR"


# -----------------------------
# FX Rate Model
# -----------------------------

@dataclass(frozen=True)
class FXRateSet:
    business_date: str               # YYYY-MM-DD
    base_currency: str               # e.g. NGN
    anchor_currency: str             # USD
    usd_to_base: float               # e.g. 1550.25 NGN/USD
    derived_rates: Dict[str, float]  # currency -> rate vs base
    source: str                      # MANUAL / REUTERS / BLOOMBERG / OTHER
    set_by: str                      # user_id
    set_at_utc: str
    locked: bool = True


# In-memory daily FX store (Phase 14; DB later)
_DAILY_FX: Dict[str, FXRateSet] = {}


def _today() -> str:
    return date.today().isoformat()


def _now_utc() -> str:
    return datetime.utcnow().isoformat()


# -----------------------------
# Treasury Operations
# -----------------------------

def set_daily_fx_rates(
    *,
    usd_to_base: float,
    other_usd_cross_rates: Dict[str, float],
    source: str,
    set_by: str,
    business_date: Optional[str] = None,
) -> FXRateSet:
    """
    Treasury/Admin sets DAILY FX.

    Inputs:
    - usd_to_base: USD -> BASE (manual input)
    - other_usd_cross_rates: e.g. {"EURO": 0.92, "POUND STERLING": 0.78}
      meaning: 1 USD = X units of that currency
    - source: MANUAL / REUTERS / BLOOMBERG
    """

    if usd_to_base <= 0:
        raise ValueError("usd_to_base must be > 0")

    if not business_date:
        business_date = _today()

    if business_date in _DAILY_FX:
        raise ValueError(f"FX rates already set and locked for {business_date}")

    derived: Dict[str, float] = {
        BASE_CURRENCY: 1.0,
        ANCHOR_CURRENCY: usd_to_base,
    }

    # Derive all other currencies vs base
    for ccy, usd_cross in other_usd_cross_rates.items():
        if usd_cross <= 0:
            raise ValueError(f"Invalid USD cross for {ccy}")
        derived[ccy.upper()] = usd_to_base / usd_cross

    fx = FXRateSet(
        business_date=business_date,
        base_currency=BASE_CURRENCY,
        anchor_currency=ANCHOR_CURRENCY,
        usd_to_base=usd_to_base,
        derived_rates=derived,
        source=source.upper(),
        set_by=set_by,
        set_at_utc=_now_utc(),
        locked=True,
    )

    _DAILY_FX[business_date] = fx
    return fx


def get_fx_rates(business_date: Optional[str] = None) -> FXRateSet:
    if not business_date:
        business_date = _today()

    fx = _DAILY_FX.get(business_date)
    if not fx:
        raise ValueError(f"No FX rates defined for {business_date}")

    return fx


def convert_to_base(
    *,
    amount: float,
    currency: str,
    business_date: Optional[str] = None,
) -> float:
    """
    Converts any currency amount into BASE currency
    using the locked daily FX rate.
    """
    fx = get_fx_rates(business_date)
    ccy = currency.upper()

    if ccy not in fx.derived_rates:
        raise ValueError(f"No FX rate for currency: {ccy}")

    return float(amount) * fx.derived_rates[ccy]


def snapshot() -> Dict[str, dict]:
    """Diagnostics / audit snapshot."""
    return {d: fx.__dict__ for d, fx in _DAILY_FX.items()}
