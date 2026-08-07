from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


LIMIT_CURRENCY = "CAD"
IDENTITY_DECISION = "IDENTITY_CAD"
ROUNDING_MODE = "DECIMAL_QUANTIZE_0_01"
_RAW_AMOUNT_FIELDS = ("notional", "amount", "exposure")
_UNIT_ONLY_FIELDS = ("units", "qty", "quantity")


@dataclass(frozen=True)
class LivePilotCurrencyAuthorityResult:
    approved: bool
    reason: str
    source_currency: str
    target_currency: str
    input_amount: Decimal | None
    converted_amount: Decimal | None
    decision: str
    identity_currency_only: bool = True
    fx_conversion_authorized: bool = False
    non_cad_live_exposure_allowed: bool = False
    rate_applied: bool = False
    rate_source: str = "NOT_AUTHORIZED"
    rate_timestamp: str = ""
    evaluation_timestamp: str = ""
    freshness_result: str = "NOT_APPLICABLE"
    rounding_mode: str = ROUNDING_MODE
    source_field: str = ""

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def evaluate_live_pilot_currency_authority(
    payload: Mapping[str, Any],
    *,
    evaluation_timestamp: str | None = None,
    limit_currency: str = LIMIT_CURRENCY,
) -> LivePilotCurrencyAuthorityResult:
    limit_ccy = str(limit_currency or "").strip().upper() or LIMIT_CURRENCY
    evaluated_at = evaluation_timestamp or _utc_now()

    amount_raw, currency_raw, source_field = _extract_authoritative_amount_and_currency(payload)

    if amount_raw is _MISSING and _has_any(payload, _UNIT_ONLY_FIELDS):
        return _reject(
            "unit_only_exposure_not_authorized",
            evaluated_at=evaluated_at,
            limit_currency=limit_ccy,
            source_field=source_field,
        )

    if amount_raw is _MISSING:
        return _reject(
            "missing_authoritative_exposure",
            evaluated_at=evaluated_at,
            limit_currency=limit_ccy,
            source_field=source_field,
        )

    if currency_raw is _MISSING or str(currency_raw).strip() == "":
        return _reject(
            "missing_exposure_currency",
            evaluated_at=evaluated_at,
            limit_currency=limit_ccy,
            source_field=source_field,
        )

    currency = str(currency_raw).strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        return _reject(
            "invalid_exposure_currency",
            evaluated_at=evaluated_at,
            limit_currency=limit_ccy,
            source_currency=currency,
            source_field=source_field,
        )

    if currency != limit_ccy:
        return _reject(
            "non_cad_exposure_not_authorized",
            evaluated_at=evaluated_at,
            limit_currency=limit_ccy,
            source_currency=currency,
            source_field=source_field,
        )

    amount = _decimal_amount(amount_raw)
    if amount is None or amount <= Decimal("0.00"):
        return _reject(
            "invalid_authoritative_exposure",
            evaluated_at=evaluated_at,
            limit_currency=limit_ccy,
            source_currency=currency,
            source_field=source_field,
        )

    return LivePilotCurrencyAuthorityResult(
        approved=True,
        reason="approved",
        source_currency=currency,
        target_currency=limit_ccy,
        input_amount=amount,
        converted_amount=amount,
        decision=IDENTITY_DECISION,
        evaluation_timestamp=evaluated_at,
        source_field=source_field,
    )


def _extract_authoritative_amount_and_currency(
    payload: Mapping[str, Any],
) -> tuple[Any, Any, str]:
    explicit = payload.get("authoritative_exposure")
    if isinstance(explicit, Mapping):
        return (
            explicit.get("amount", _MISSING),
            explicit.get("currency", _MISSING),
            "authoritative_exposure",
        )

    has_explicit_currency = "authoritative_exposure_currency" in payload
    has_explicit_amount = "authoritative_exposure_amount" in payload

    if has_explicit_currency or has_explicit_amount:
        amount = payload.get("authoritative_exposure_amount", _MISSING)
        source_field = "authoritative_exposure_amount"
        if amount is _MISSING:
            for key in _RAW_AMOUNT_FIELDS:
                if key in payload:
                    amount = payload.get(key)
                    source_field = key
                    break
        return (
            amount,
            payload.get("authoritative_exposure_currency", _MISSING),
            source_field,
        )

    if _has_any(payload, _RAW_AMOUNT_FIELDS):
        for key in _RAW_AMOUNT_FIELDS:
            if key in payload:
                return (payload.get(key), _MISSING, key)

    if _has_any(payload, _UNIT_ONLY_FIELDS):
        return (_MISSING, _MISSING, "")

    return (_MISSING, _MISSING, "")


def _decimal_amount(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite():
        return None
    return amount


def _has_any(payload: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(key in payload for key in keys)


def _reject(
    reason: str,
    *,
    evaluated_at: str,
    limit_currency: str,
    source_currency: str = "",
    source_field: str = "",
) -> LivePilotCurrencyAuthorityResult:
    return LivePilotCurrencyAuthorityResult(
        approved=False,
        reason=reason,
        source_currency=source_currency,
        target_currency=limit_currency,
        input_amount=None,
        converted_amount=None,
        decision="REJECT",
        evaluation_timestamp=evaluated_at,
        source_field=source_field,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


_MISSING = object()


__all__ = [
    "IDENTITY_DECISION",
    "LIMIT_CURRENCY",
    "LivePilotCurrencyAuthorityResult",
    "ROUNDING_MODE",
    "evaluate_live_pilot_currency_authority",
]