"""Non-executing currency conversion for governed pilot risk screening.

Rates are *supplied*, never fetched or trusted here. Broker provenance, ISO
currency eligibility, account permissions, and quote signatures must be
validated independently before integrating with any order submission path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import re

_CENT = Decimal("0.01")
_CODE = re.compile(r"^[A-Z]{3}$")


class PilotCurrencyError(ValueError):
    pass


def _number(value: object, *, positive: bool = True) -> Decimal:
    if isinstance(value, bool):
        raise PilotCurrencyError("boolean amount")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PilotCurrencyError("invalid number") from exc
    if not n.is_finite() or (n <= 0 if positive else n < 0):
        raise PilotCurrencyError("invalid number")
    return n


def _code(raw: str) -> str:
    if type(raw) is not str or not _CODE.fullmatch(raw):
        raise PilotCurrencyError("invalid ISO-style currency code")
    return raw


@dataclass(frozen=True)
class PilotRiskBudget:
    currency: str
    max_parent: Decimal
    max_aggregate: Decimal

    def __post_init__(self) -> None:
        _code(self.currency)
        if type(self.max_parent) is not Decimal or type(self.max_aggregate) is not Decimal:
            raise PilotCurrencyError("budget amounts must be Decimal")
        _number(self.max_parent)
        _number(self.max_aggregate)
        if self.max_aggregate < self.max_parent:
            raise PilotCurrencyError("aggregate below parent limit")


CURRENT_PILOT_BUDGET = PilotRiskBudget("CAD", Decimal("20.00"), Decimal("40.00"))


@dataclass(frozen=True)
class VerifiedRateInput:
    base_currency: str
    quote_currency: str
    quote_per_base: Decimal
    observed_at: datetime
    source_id: str

    def __post_init__(self) -> None:
        _code(self.base_currency)
        _code(self.quote_currency)
        if self.base_currency == self.quote_currency:
            raise PilotCurrencyError("same-currency rates not needed")
        if type(self.quote_per_base) is not Decimal:
            raise PilotCurrencyError("rate must be Decimal")
        _number(self.quote_per_base)
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None:
            raise PilotCurrencyError("timezone-aware rate timestamp required")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise PilotCurrencyError("source id required")


def convert_risk_up(
    amount: object,
    *,
    source_currency: str,
    budget: PilotRiskBudget,
    rate: VerifiedRateInput | None = None,
    now: datetime | None = None,
    maximum_age: timedelta = timedelta(seconds=30),
) -> Decimal:
    """Convert risk upward, requiring a fresh direct source->budget rate.

    This function is *not* the proof that a rate is trusted. Callers must
    independently verify source signatures, broker permissions and rate origin.
    No automatic inversion or triangulation is allowed.
    """
    source = _code(source_currency)
    value = _number(amount, positive=False)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise PilotCurrencyError("timezone-aware current time required")
    if not isinstance(maximum_age, timedelta) or not timedelta(0) < maximum_age <= timedelta(minutes=5):
        raise PilotCurrencyError("unacceptable rate age policy")
    if source == budget.currency:
        if rate is not None:
            raise PilotCurrencyError("extraneous rate for same currency")
        converted = value
    else:
        if type(rate) is not VerifiedRateInput or rate.base_currency != source or rate.quote_currency != budget.currency:
            raise PilotCurrencyError("exact directed FX pair unavailable")
        age = current.astimezone(timezone.utc) - rate.observed_at.astimezone(timezone.utc)
        if age < timedelta(0) or age > maximum_age:
            raise PilotCurrencyError("stale or future rate")
        converted = value * rate.quote_per_base
    if not converted.is_finite():
        raise PilotCurrencyError("non-finite result")
    return converted.quantize(_CENT, rounding=ROUND_CEILING)
