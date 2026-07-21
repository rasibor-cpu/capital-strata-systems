"""Phase 178A — collateral authority hierarchy for Options Income.

Never treat the historical simulated 10,000 margin fixture as genuine collateral.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from backend.options.options_income_advisory_contracts import collateral_envelope
from backend.options.options_income_freshness import utc_now

# Authority levels (highest first)
AUTHORITY_BROKER = "BROKER_REPORTED"
AUTHORITY_HOLDINGS = "ACCOUNT_HOLDINGS_CASH"
AUTHORITY_DERIVED = "CSS_DERIVED_ADVISORY"
AUTHORITY_UNAVAILABLE = "UNAVAILABLE"

SIMULATED_FIXTURE_MARKERS = {
    "fixture",
    "smoke",
    "demo",
    "demonstration",
    "simulated_10000",
    "css_smoke_cash",
}


def resolve_collateral_authority(
    *,
    broker_collateral: Mapping[str, Any] | None = None,
    holdings: Mapping[str, Any] | None = None,
    css_derived: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the highest reliable collateral envelope."""
    ts = generated_at or utc_now()

    broker = dict(broker_collateral or {})
    if _broker_collateral_reliable(broker):
        return collateral_envelope(
            generated_at=ts,
            status="READY",
            authority_level=AUTHORITY_BROKER,
            source=str(broker.get("source") or "BROKER"),
            provenance="BROKER",
            currency=broker.get("currency"),
            value=float(broker["value"]),
            calculation_basis=broker.get("calculation_basis") or "broker_reported_buying_power_or_collateral",
            timestamp=broker.get("timestamp") or ts,
            haircut_or_reserve=broker.get("haircut_or_reserve"),
            broker_confirmed=True,
            css_derived=False,
        )

    hold = dict(holdings or {})
    cash = hold.get("cash")
    bp = hold.get("buying_power")
    value = bp if bp is not None else cash
    if _holdings_collateral_reliable(hold, value):
        return collateral_envelope(
            generated_at=ts,
            status=str(hold.get("status")).upper(),
            authority_level=AUTHORITY_HOLDINGS,
            source="ACCOUNT_HOLDINGS",
            provenance="ACCOUNT_HOLDINGS",
            currency=hold.get("base_currency"),
            value=float(value),
            calculation_basis="holdings.cash_or_buying_power",
            timestamp=hold.get("provider_timestamp") or ts,
            haircut_or_reserve=hold.get("haircut_or_reserve"),
            broker_confirmed=False,
            css_derived=False,
        )

    derived = dict(css_derived or {})
    if derived.get("value") is not None and not _is_simulated_fixture(derived):
        return collateral_envelope(
            generated_at=ts,
            status="DERIVED",
            authority_level=AUTHORITY_DERIVED,
            source="CSS_DERIVED",
            provenance="DERIVED",
            currency=derived.get("currency"),
            value=float(derived["value"]),
            calculation_basis=derived.get("calculation_basis") or "css_advisory_estimate",
            timestamp=derived.get("timestamp") or ts,
            haircut_or_reserve=derived.get("haircut_or_reserve"),
            broker_confirmed=False,
            css_derived=True,
        )

    return collateral_envelope(
        generated_at=ts,
        status="UNAVAILABLE",
        authority_level=AUTHORITY_UNAVAILABLE,
        source="UNAVAILABLE",
        provenance="CONFIGURATION",
        currency=None,
        value=None,
        calculation_basis=None,
        timestamp=ts,
        haircut_or_reserve=None,
        broker_confirmed=False,
        css_derived=False,
        failure_reason="no_traceable_collateral_source",
    )


def _is_simulated_fixture(row: Mapping[str, Any]) -> bool:
    """Reject known demo/smoke fixtures — not every numeric 10000 from a real account."""
    blob = " ".join(
        str(row.get(k) or "").lower()
        for k in ("source", "provenance", "calculation_basis", "fixture_id", "note", "status")
    )
    if any(m in blob for m in SIMULATED_FIXTURE_MARKERS):
        return True
    if bool(row.get("demonstration")) or bool(row.get("is_fixture")):
        return True
    return False


def _valid_nonnegative_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0


def _broker_collateral_reliable(row: Mapping[str, Any]) -> bool:
    if not row or _is_simulated_fixture(row) or not _valid_nonnegative_number(row.get("value")):
        return False
    if str(row.get("status") or "").upper() not in {"READY", "AVAILABLE", "CONFIRMED"}:
        return False
    if str(row.get("provenance") or "").upper() not in {"BROKER", "BROKER_API"}:
        return False
    if not row.get("currency") or not (row.get("timestamp") or row.get("provider_timestamp")):
        return False
    return not bool(row.get("stale")) and str(row.get("freshness") or "").upper() != "STALE"


def _holdings_collateral_reliable(row: Mapping[str, Any], value: Any) -> bool:
    if not row or _is_simulated_fixture(row) or not _valid_nonnegative_number(value):
        return False
    if str(row.get("status") or "").upper() not in {"READY", "PARTIAL_DATA"}:
        return False
    if str(row.get("provenance") or "").upper() not in {"ACCOUNT_HOLDINGS", "BROKER"}:
        return False
    return bool(row.get("base_currency")) and not bool(row.get("stale"))


__all__ = [
    "AUTHORITY_BROKER",
    "AUTHORITY_DERIVED",
    "AUTHORITY_HOLDINGS",
    "AUTHORITY_UNAVAILABLE",
    "resolve_collateral_authority",
]
