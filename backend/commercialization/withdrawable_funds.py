from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence, Tuple


_REASON_ORDER = (
    "UNSETTLED_PROCEEDS",
    "OPEN_ORDER_RESERVE",
    "MARGIN_OR_POSITION_RESERVE",
    "PENDING_CSS_CHARGE",
    "OTHER_KNOWN_RESTRICTION",
    "INCOMPLETE_BROKER_DATA",
    "STALE_BROKER_DATA",
    "CURRENCY_CONVERSION_REQUIRED",
)


def _coerce_decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, (int, float, str)):
        try:
            dec = Decimal(str(value))
        except InvalidOperation as exc:
            raise TypeError(f"{field_name} must be a Decimal-compatible value") from exc
    else:
        raise TypeError(f"{field_name} must be Decimal-like or None")
    if not dec.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return dec


def _canonical_reason_codes(values: Iterable[str]) -> Tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        code = str(value)
        if code in seen:
            continue
        seen.add(code)
        if code in _REASON_ORDER:
            ordered.append(code)
        else:
            ordered.append(code)
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class CommercialWithdrawableFundsSummary:
    """Immutable read-only advisory model for broker withdrawal availability."""

    account_reference: str
    account_currency: str
    as_of: str
    total_cash: Decimal | None
    settled_cash: Decimal | None
    unsettled_proceeds: Decimal | None
    reserved_for_open_orders: Decimal | None
    reserved_for_margin_or_positions: Decimal | None
    pending_css_charge: Decimal | None
    other_restricted_amount: Decimal | None
    total_restricted_amount: Decimal | None
    available_to_withdraw: Decimal | None
    data_freshness: str
    is_complete: bool
    restriction_reasons: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.account_reference or self.account_reference != self.account_reference.strip():
            raise ValueError("account_reference must be canonical")
        if not self.account_currency or self.account_currency != self.account_currency.upper():
            raise ValueError("account_currency must be canonical uppercase ISO code")
        if not self.as_of or self.as_of != self.as_of.strip():
            raise ValueError("as_of must be a canonical timestamp")

        for name in (
            "total_cash",
            "settled_cash",
            "unsettled_proceeds",
            "reserved_for_open_orders",
            "reserved_for_margin_or_positions",
            "pending_css_charge",
            "other_restricted_amount",
            "total_restricted_amount",
            "available_to_withdraw",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            value = _coerce_decimal(value, name)
            object.__setattr__(self, name, value)
            if value < 0:
                raise ValueError(f"{name} cannot be negative")

        if not isinstance(self.restriction_reasons, tuple):
            raise TypeError("restriction_reasons must be tuple")
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be tuple")

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_withdrawable_funds_summary(
    *,
    account_reference: str,
    account_currency: str,
    as_of: str,
    total_cash: Decimal | None = None,
    settled_cash: Decimal | None = None,
    unsettled_proceeds: Decimal | None = None,
    reserved_for_open_orders: Decimal | None = None,
    reserved_for_margin_or_positions: Decimal | None = None,
    pending_css_charge: Decimal | None = None,
    other_restricted_amount: Decimal | None = None,
    total_restricted_amount: Decimal | None = None,
    available_to_withdraw: Decimal | None = None,
    data_freshness: str = "UNKNOWN",
    is_complete: bool = False,
    restriction_reasons: Sequence[str] | None = None,
    evidence_refs: Sequence[str] | None = None,
) -> CommercialWithdrawableFundsSummary:
    """Construct a fail-closed advisory summary from canonical read-only broker state."""

    decimals = {
        "total_cash": _coerce_decimal(total_cash, "total_cash"),
        "settled_cash": _coerce_decimal(settled_cash, "settled_cash"),
        "unsettled_proceeds": _coerce_decimal(unsettled_proceeds, "unsettled_proceeds"),
        "reserved_for_open_orders": _coerce_decimal(reserved_for_open_orders, "reserved_for_open_orders"),
        "reserved_for_margin_or_positions": _coerce_decimal(
            reserved_for_margin_or_positions,
            "reserved_for_margin_or_positions",
        ),
        "pending_css_charge": _coerce_decimal(pending_css_charge, "pending_css_charge"),
        "other_restricted_amount": _coerce_decimal(other_restricted_amount, "other_restricted_amount"),
    }

    if total_restricted_amount is None:
        restricted = [
            value for value in (
                decimals["reserved_for_open_orders"],
                decimals["reserved_for_margin_or_positions"],
                decimals["pending_css_charge"],
                decimals["other_restricted_amount"],
            ) if value is not None
        ]
        total_restricted_amount = sum(restricted, Decimal("0")) if restricted else None

    if available_to_withdraw is None and decimals["settled_cash"] is not None:
        amount = decimals["settled_cash"]
        for key in (
            "reserved_for_open_orders",
            "reserved_for_margin_or_positions",
            "pending_css_charge",
            "other_restricted_amount",
        ):
            value = decimals[key]
            if value is not None:
                amount -= value
        available_to_withdraw = max(amount, Decimal("0"))

    if restriction_reasons is None:
        reasons: list[str] = []
        if decimals["unsettled_proceeds"] not in (None, Decimal("0")):
            reasons.append("UNSETTLED_PROCEEDS")
        if decimals["reserved_for_open_orders"] not in (None, Decimal("0")):
            reasons.append("OPEN_ORDER_RESERVE")
        if decimals["reserved_for_margin_or_positions"] not in (None, Decimal("0")):
            reasons.append("MARGIN_OR_POSITION_RESERVE")
        if decimals["pending_css_charge"] not in (None, Decimal("0")):
            reasons.append("PENDING_CSS_CHARGE")
        if decimals["other_restricted_amount"] not in (None, Decimal("0")):
            reasons.append("OTHER_KNOWN_RESTRICTION")
        if not is_complete:
            reasons.append("INCOMPLETE_BROKER_DATA")
        if str(data_freshness).upper() == "STALE":
            reasons.append("STALE_BROKER_DATA")
        if any(value is None for value in (
            total_cash,
            settled_cash,
            reserved_for_open_orders,
            reserved_for_margin_or_positions,
            pending_css_charge,
            other_restricted_amount,
        )):
            is_complete = False
        restriction_reasons = _canonical_reason_codes(reasons)
    else:
        restriction_reasons = _canonical_reason_codes(restriction_reasons)

    if evidence_refs is None:
        evidence_refs = ()

    return CommercialWithdrawableFundsSummary(
        account_reference=account_reference,
        account_currency=account_currency,
        as_of=as_of,
        total_cash=decimals["total_cash"],
        settled_cash=decimals["settled_cash"],
        unsettled_proceeds=decimals["unsettled_proceeds"],
        reserved_for_open_orders=decimals["reserved_for_open_orders"],
        reserved_for_margin_or_positions=decimals["reserved_for_margin_or_positions"],
        pending_css_charge=decimals["pending_css_charge"],
        other_restricted_amount=decimals["other_restricted_amount"],
        total_restricted_amount=total_restricted_amount,
        available_to_withdraw=available_to_withdraw,
        data_freshness=str(data_freshness).upper(),
        is_complete=bool(is_complete),
        restriction_reasons=tuple(restriction_reasons),
        evidence_refs=tuple(str(ref) for ref in evidence_refs),
    )


def build_client_earnings_history(
    records: Iterable[Mapping[str, Any] | Any] | Mapping[str, Any] | Any,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Return period history records in deterministic period order."""

    def normalize(record: Mapping[str, Any] | Any) -> dict[str, Any]:
        if isinstance(record, Mapping):
            raw = dict(record)
        elif hasattr(record, "__dict__"):
            raw = vars(record).copy()
        else:
            raise TypeError("record must be a mapping-like object")

        return {
            "period_start": raw.get("period_start"),
            "period_end": raw.get("period_end"),
            "account_reference": raw.get("account_reference"),
            "policy_id": raw.get("policy_id"),
            "terms_id": raw.get("terms_id"),
            "performance_currency": raw.get("performance_currency"),
            "billing_currency": raw.get("billing_currency"),
            "realized_attributable_profit": _coerce_decimal(
                raw.get("realized_attributable_profit"), "realized_attributable_profit",
            ),
            "recovered_loss": _coerce_decimal(raw.get("recovered_loss"), "recovered_loss"),
            "new_economic_gain": _coerce_decimal(raw.get("new_economic_gain"), "new_economic_gain"),
            "performance_fee_rate": _coerce_decimal(raw.get("performance_fee_rate"), "performance_fee_rate"),
            "performance_fee_source_amount": _coerce_decimal(
                raw.get("performance_fee_source_amount"), "performance_fee_source_amount",
            ),
            "performance_fee_billing_currency_amount": _coerce_decimal(
                raw.get("performance_fee_billing_currency_amount"),
                "performance_fee_billing_currency_amount",
            ),
            "platform_access_fee_amount": _coerce_decimal(
                raw.get("platform_access_fee_amount"), "platform_access_fee_amount",
            ),
            "access_terms_id": raw.get("access_terms_id"),
            "selected_fee_basis": raw.get("selected_fee_basis"),
            "selected_fee_amount": _coerce_decimal(raw.get("selected_fee_amount"), "selected_fee_amount"),
            "final_fee_selection_id": raw.get("final_fee_selection_id"),
            "net_earnings_after_css_fee": _coerce_decimal(
                raw.get("net_earnings_after_css_fee"), "net_earnings_after_css_fee",
            ),
            "fx_rate": _coerce_decimal(raw.get("fx_rate"), "fx_rate"),
            "fx_conversion_id": raw.get("fx_conversion_id"),
            "fx_rate_source_reference": raw.get("fx_rate_source_reference"),
            "invoice_id": raw.get("invoice_id"),
            "receivable_id": raw.get("receivable_id"),
            "evidence_refs": tuple(str(ref) for ref in raw.get("evidence_refs", ())),
        }

    if isinstance(records, Mapping):
        return normalize(records)
    if records is None:
        return []
    if isinstance(records, (str, bytes)):
        raise TypeError("record must be a mapping-like object")

    entries = [normalize(record) for record in records]
    return sorted(entries, key=lambda item: (item.get("period_start") or "", item.get("period_end") or ""))
