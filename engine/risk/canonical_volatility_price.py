"""Canonical price validation for volatility position sizing (MW-003)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional


REASON_MISSING = "volatility_price_missing"
REASON_INVALID = "volatility_price_invalid"
REASON_STALE = "volatility_price_stale"
REASON_INSTRUMENT_MISMATCH = "volatility_price_instrument_mismatch"


def coerce_finite_positive_price(value: Any) -> Optional[float]:
    """Return a finite price > 0, else None. Does not invent defaults."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if number <= 0.0:
        return None
    return number


def resolve_canonical_price_candidates(
    *,
    price: Any = None,
    last_price: Any = None,
    reference_price: Any = None,
    market_price: Any = None,
    mid_price: Any = None,
    current_price: Any = None,
) -> tuple[Optional[float], Optional[str]]:
    """
    Precedence (first valid wins):
    price → last_price → market_price → mid_price → reference_price → current_price
    """
    ordered = (
        ("price", price),
        ("last_price", last_price),
        ("market_price", market_price),
        ("mid_price", mid_price),
        ("reference_price", reference_price),
        ("current_price", current_price),
    )
    for name, raw in ordered:
        parsed = coerce_finite_positive_price(raw)
        if parsed is not None:
            return parsed, name
    return None, None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def validate_canonical_price_for_volatility(
    *,
    instrument: str,
    price: Any = None,
    last_price: Any = None,
    reference_price: Any = None,
    market_price: Any = None,
    mid_price: Any = None,
    current_price: Any = None,
    price_instrument: Any = None,
    price_as_of: Any = None,
    price_max_age_seconds: Any = None,
    now: Optional[datetime] = None,
) -> tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Validate canonical price for ExecutionGate volatility sizing.

    Returns: (price, source_field, reason_code)
    On success reason_code is None.
    """
    canonical, source = resolve_canonical_price_candidates(
        price=price,
        last_price=last_price,
        reference_price=reference_price,
        market_price=market_price,
        mid_price=mid_price,
        current_price=current_price,
    )
    if canonical is None:
        # Distinguish totally absent vs present-but-invalid raw inputs.
        raw_present = any(
            value is not None and str(value).strip() != ""
            for value in (price, last_price, reference_price, market_price, mid_price, current_price)
        )
        return None, None, REASON_INVALID if raw_present else REASON_MISSING

    if price_instrument is not None and str(price_instrument).strip():
        expected = str(instrument or "").strip().upper()
        provided = str(price_instrument).strip().upper()
        if expected and provided and expected != provided:
            return None, source, REASON_INSTRUMENT_MISMATCH

    if price_max_age_seconds is not None and str(price_max_age_seconds).strip() != "":
        try:
            max_age = float(price_max_age_seconds)
        except (TypeError, ValueError):
            return None, source, REASON_INVALID
        if not math.isfinite(max_age) or max_age < 0:
            return None, source, REASON_INVALID
        as_of = _parse_timestamp(price_as_of)
        if as_of is None:
            # Freshness contract requested but timestamp unavailable → treat as stale/unenforcible fail-closed.
            return None, source, REASON_STALE
        current = now or datetime.now(timezone.utc)
        age = (current - as_of).total_seconds()
        if age < 0 or age > max_age:
            return None, source, REASON_STALE

    return canonical, source, None


__all__ = [
    "REASON_INSTRUMENT_MISMATCH",
    "REASON_INVALID",
    "REASON_MISSING",
    "REASON_STALE",
    "coerce_finite_positive_price",
    "resolve_canonical_price_candidates",
    "validate_canonical_price_for_volatility",
]
