"""CSS-062 G3 conservative normalization contract tests (review-only helper)."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from backend.runtime.css062_cad_binding import CadBindingError, normalize_approved_cad


NOW = datetime(2026, 10, 13, 17, 0, tzinfo=timezone.utc)


def _inputs():
    return dict(
        signed_order={"instrument": "EURUSD", "broker": "OANDA", "currency": "USD", "reserved_cad": "13.20"},
        approved_notional="10.00",
        approved_currency="USD",
        conversion_rate_to_cad="1.30",
        conversion_observed_at=NOW.isoformat(),
        estimated_fees_cad="0.20",
        expected_instrument="EURUSD",
        expected_broker="OANDA",
        now=NOW,
    )


def test_exact_fee_inclusive_cad():
    assert normalize_approved_cad(**_inputs()) == Decimal("13.20")


@pytest.mark.parametrize("field,value", [
    ("approved_notional", "NaN"),
    ("conversion_rate_to_cad", "Infinity"),
    ("conversion_rate_to_cad", "0"),
    ("estimated_fees_cad", "-0.01"),
    ("approved_notional", True),
    ("conversion_observed_at", (NOW - timedelta(seconds=61)).isoformat()),
    ("conversion_observed_at", (NOW + timedelta(seconds=1)).isoformat()),
    ("expected_broker", "Coinbase"),
    ("expected_instrument", "BTCUSD"),
    ("approved_currency", "EUR"),
])
def test_invalid_or_mismatched_evidence_fails_closed(field, value):
    data = _inputs()
    data[field] = value
    with pytest.raises(CadBindingError):
        normalize_approved_cad(**data)


def test_under_reservation_rejected():
    data = _inputs()
    data["signed_order"]["reserved_cad"] = "0.01"
    with pytest.raises(CadBindingError, match="under-reservation"):
        normalize_approved_cad(**data)


def test_rounds_up_not_down():
    data = _inputs()
    data["approved_notional"] = "0.011"
    data["conversion_rate_to_cad"] = "1.30"
    data["estimated_fees_cad"] = "0"
    assert normalize_approved_cad(**data) == Decimal("0.02")


def test_cad_requires_unit_conversion():
    data = _inputs()
    data["approved_currency"] = "CAD"
    data["signed_order"]["currency"] = "CAD"
    with pytest.raises(CadBindingError, match="CAD rate"):
        normalize_approved_cad(**data)
