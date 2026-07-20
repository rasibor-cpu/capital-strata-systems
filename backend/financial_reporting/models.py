"""Phase 177 — shared financial reporting models (Decimal-safe)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any


MONEY_QUANT = Decimal("0.01")
RATIO_QUANT = Decimal("0.0001")


class ReportingPeriodType(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEAR_TO_DATE = "YEAR_TO_DATE"
    ANNUAL = "ANNUAL"
    CUSTOM = "CUSTOM"


class MissingReason(str, Enum):
    ZERO = "zero"
    UNAVAILABLE = "unavailable"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class ReadinessState(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    NOT_READY = "NOT_READY"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class TrafficLight(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


def d(value: Any) -> Decimal:
    """Coerce to Decimal; raises for invalid input."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        raise TypeError("None is not a Decimal")
    return Decimal(str(value))


def money(value: Any) -> Decimal:
    return d(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def ratio(value: Any) -> Decimal:
    return d(value).quantize(RATIO_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FinancialAmount:
    """
    Explicit amount with availability semantics.

    - present=True, value=0 → true zero
    - present=False → unavailable / missing / N/A (value ignored for totals)
    """

    present: bool
    value: Decimal = field(default_factory=lambda: Decimal("0.00"))
    reason: MissingReason = MissingReason.ZERO
    currency: str = "USD"
    source: str | None = None

    @classmethod
    def zero(cls, *, currency: str = "USD", source: str | None = None) -> FinancialAmount:
        return cls(present=True, value=money(0), reason=MissingReason.ZERO, currency=currency, source=source)

    @classmethod
    def of(
        cls,
        value: Any,
        *,
        currency: str = "USD",
        source: str | None = None,
    ) -> FinancialAmount:
        return cls(present=True, value=money(value), reason=MissingReason.ZERO, currency=currency, source=source)

    @classmethod
    def missing(
        cls,
        reason: MissingReason = MissingReason.MISSING,
        *,
        currency: str = "USD",
        source: str | None = None,
    ) -> FinancialAmount:
        if reason == MissingReason.ZERO:
            return cls.zero(currency=currency, source=source)
        return cls(present=False, value=money(0), reason=reason, currency=currency, source=source)

    def for_total(self) -> Decimal | None:
        """Return numeric contribution, or None when unavailable (do not coerce to healthy zero)."""
        if not self.present:
            return None
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "value": format(self.value, "f") if self.present else None,
            "reason": self.reason.value,
            "currency": self.currency,
            "source": self.source,
        }


def sum_amounts(*amounts: FinancialAmount) -> tuple[Decimal, bool, list[str]]:
    """
    Sum present amounts.

    Returns (total, complete, missing_fields_markers).
    complete=False when any amount is not present.
    """
    total = money(0)
    complete = True
    missing: list[str] = []
    for i, amt in enumerate(amounts):
        contrib = amt.for_total()
        if contrib is None:
            complete = False
            missing.append(f"slot_{i}:{amt.reason.value}")
        else:
            total += contrib
    return money(total), complete, missing


def serialize_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(money(value), "f")


def deep_freeze_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe deep copy (Decimals → strings)."""
    import copy
    import json

    def _default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return format(obj, "f")
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(type(obj).__name__)

    return json.loads(json.dumps(payload, default=_default))
