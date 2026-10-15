"""CSS-062 G3: fail-closed CAD exposure normalization for simulation review.

Pure validation only. Not wired to a broker, reservation ledger, or production route.
The caller must separately establish provenance of broker, instrument, and FX data.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, DecimalException, InvalidOperation, Inexact, ROUND_UP, localcontext
from collections.abc import Mapping


class CadBindingError(ValueError):
    """Risk-approved exposure cannot be proven."""


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise CadBindingError(f"{label}: unsupported numeric type")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CadBindingError(f"{label}: invalid amount") from exc
    if not result.is_finite() or result < 0:
        raise CadBindingError(f"{label}: nonfinite or negative")
    return result


def normalize_approved_cad(
    *,
    signed_order: Mapping[str, object],
    approved_notional: object,
    approved_currency: str,
    conversion_rate_to_cad: object,
    conversion_observed_at: str,
    estimated_fees_cad: object,
    expected_instrument: str,
    expected_broker: str,
    now: datetime | None = None,
    max_rate_age_seconds: int = 60,
) -> Decimal:
    """Return conservative fee-inclusive CAD exposure; reject ambiguous evidence.

    Conversion rate means CAD per one unit of approved_currency. The trusted
    caller must verify the source/authenticity of the inputs before using this
    helper; a caller-supplied timestamp or rate alone is NOT authenticated.
    """
    if not isinstance(signed_order, Mapping):
        raise CadBindingError("signed order missing")
    if not expected_instrument or signed_order.get("instrument") != expected_instrument:
        raise CadBindingError("instrument mismatch")
    if not expected_broker or signed_order.get("broker") != expected_broker:
        raise CadBindingError("broker mismatch")
    if not isinstance(approved_currency, str) or not approved_currency.strip():
        raise CadBindingError("currency missing")
    # Canonical ASCII currency codes prevent CAD parity bypass via aliases.
    if not (approved_currency.isascii() and approved_currency.isalnum() and approved_currency.isupper()):
        raise CadBindingError("noncanonical currency code")
    if signed_order.get("currency") != approved_currency:
        raise CadBindingError("approved currency mismatch")
    notional = _decimal(approved_notional, "approved_notional")
    fees = _decimal(estimated_fees_cad, "fees")
    rate = _decimal(conversion_rate_to_cad, "conversion_rate_to_cad")
    if notional <= 0 or rate <= 0:
        raise CadBindingError("notional and rate must be positive")
    if approved_currency == "CAD" and rate != 1:
        raise CadBindingError("CAD rate must equal one")
    if type(max_rate_age_seconds) is not int or not 0 < max_rate_age_seconds <= 300:
        raise CadBindingError("invalid freshness policy")
    try:
        observed = datetime.fromisoformat(conversion_observed_at)
    except (TypeError, ValueError) as exc:
        raise CadBindingError("invalid FX timestamp") from exc
    if observed.tzinfo is None:
        raise CadBindingError("FX timestamp must be timezone-aware")
    # Never replace an explicitly invalid clock with wall time.
    if now is not None and not isinstance(now, datetime):
        raise CadBindingError("invalid explicit clock")
    clock = datetime.now(timezone.utc) if now is None else now
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise CadBindingError("clock must be timezone-aware")
    age = clock - observed
    if age < timedelta(0) or age > timedelta(seconds=max_rate_age_seconds):
        raise CadBindingError("stale or future FX evidence")
    try:
        # Multiplication/addition must be exact before the intentional
        # outward rounding to cents. The default Decimal context (28 digits)
        # can otherwise discard a tiny positive exposure and under-reserve.
        with localcontext() as exact_context:
            exact_context.traps[Inexact] = True
            exact_exposure = notional * rate + fees
        expected = exact_exposure.quantize(Decimal("0.01"), rounding=ROUND_UP)
    except (DecimalException, OverflowError, ValueError) as exc:
        # Fail closed with a typed governance error, not an unhandled decimal trap.
        raise CadBindingError("CAD exposure cannot be represented") from exc
    reserved = _decimal(signed_order.get("reserved_cad"), "reserved_cad")
    if reserved < expected:
        raise CadBindingError("under-reservation against approved notional")
    return expected
