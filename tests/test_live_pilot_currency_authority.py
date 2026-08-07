from __future__ import annotations

import socket
from decimal import Decimal

import pytest

from backend.app.live_pilot_currency_authority import (
    IDENTITY_DECISION,
    LIMIT_CURRENCY,
    evaluate_live_pilot_currency_authority,
)


def _cad_payload(amount: str = "20.00") -> dict[str, str]:
    return {
        "authoritative_exposure_amount": amount,
        "authoritative_exposure_currency": "CAD",
    }


def test_explicit_cad_identity_is_deterministic_and_rate_free() -> None:
    result = evaluate_live_pilot_currency_authority(_cad_payload("10.00"))

    assert result.approved is True
    assert result.decision == IDENTITY_DECISION
    assert result.source_currency == "CAD"
    assert result.target_currency == LIMIT_CURRENCY
    assert result.input_amount == Decimal("10.00")
    assert result.converted_amount == Decimal("10.00")
    assert result.rate_applied is False
    assert result.fx_conversion_authorized is False
    assert result.rate_source == "NOT_AUTHORIZED"
    assert result.freshness_result == "NOT_APPLICABLE"


def test_non_cad_exposure_fails_closed() -> None:
    result = evaluate_live_pilot_currency_authority(
        {"authoritative_exposure_amount": "10.00", "authoritative_exposure_currency": "USD"}
    )

    assert result.approved is False
    assert result.reason == "non_cad_exposure_not_authorized"


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"authoritative_exposure_amount": "10.00"}, "missing_exposure_currency"),
        ({"authoritative_exposure_amount": "10.00", "authoritative_exposure_currency": ""}, "missing_exposure_currency"),
        ({"authoritative_exposure_amount": "10.00", "authoritative_exposure_currency": "cad$"}, "invalid_exposure_currency"),
        ({"authoritative_exposure_currency": "CAD"}, "missing_authoritative_exposure"),
        ({"authoritative_exposure_amount": "abc", "authoritative_exposure_currency": "CAD"}, "invalid_authoritative_exposure"),
        ({"authoritative_exposure_amount": "NaN", "authoritative_exposure_currency": "CAD"}, "invalid_authoritative_exposure"),
        ({"authoritative_exposure_amount": "Infinity", "authoritative_exposure_currency": "CAD"}, "invalid_authoritative_exposure"),
        ({"authoritative_exposure_amount": "-1.00", "authoritative_exposure_currency": "CAD"}, "invalid_authoritative_exposure"),
        ({"units": "1000", "authoritative_exposure_currency": "CAD"}, "unit_only_exposure_not_authorized"),
        ({"notional": "10.00", "account_currency": "CAD"}, "missing_exposure_currency"),
        ({"amount": "10.00", "symbol": "EUR_USD"}, "missing_exposure_currency"),
    ],
)
def test_fail_closed_paths(payload, reason) -> None:
    result = evaluate_live_pilot_currency_authority(payload)

    assert result.approved is False
    assert result.reason == reason


def test_explicit_legacy_mapping_requires_explicit_cad_currency() -> None:
    result = evaluate_live_pilot_currency_authority(
        {"notional": "9.99", "authoritative_exposure_currency": "CAD"}
    )

    assert result.approved is True
    assert result.source_field == "notional"
    assert result.converted_amount == Decimal("9.99")


def test_fx_daily_rates_is_not_invoked(monkeypatch) -> None:
    import backend.app.fx_daily_rates as fx_daily_rates

    monkeypatch.setattr(
        fx_daily_rates,
        "get_fx_rate",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fx rate lookup must not be called")),
    )

    result = evaluate_live_pilot_currency_authority(_cad_payload("1.00"))

    assert result.approved is True


def test_no_network_call_occurs(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network must not be called")),
    )

    result = evaluate_live_pilot_currency_authority(_cad_payload("1.00"))

    assert result.approved is True