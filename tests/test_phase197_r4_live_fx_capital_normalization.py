from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.market.fx_conversion_contract import FXConversionQuote
from backend.app.market.provider_interfaces import UnavailableFXConversionProvider
from backend.runtime.live_micro_pilot_governor import (
    LiveMicroPilotAuthorizationError,
    LiveMicroPilotGovernor,
)


SUPER_USER = {"user_id": "00000", "role": "SUPER_USER"}


class StaticFXProvider:
    def __init__(self, rate: float):
        self.rate = rate

    def get_conversion(self, *, base_currency, quote_currency, context=None):
        return FXConversionQuote(
            base_currency=base_currency,
            quote_currency=quote_currency,
            rate=self.rate,
            timestamp="2026-08-10T00:00:00Z",
            provider="PHASE197_TEST",
            provider_version="197.R4",
            quality="CERTIFIED",
            status="AVAILABLE",
            conversion_path=(f"{base_currency}/{quote_currency}",),
            path_type="DIRECT",
            contributing_rate_ids=("PHASE197_TEST_RATE",),
            contributing_provider_ids=("PHASE197_TEST",),
            contributing_timestamps=("2026-08-10T00:00:00Z",),
            evidence_hash="phase197-test-evidence",
            fail_reason="",
        )


def make_governor(tmp_path: Path, provider=None):
    governor = LiveMicroPilotGovernor(
        config_path=tmp_path / "pilot_config.json",
        state_path=tmp_path / "pilot_state.json",
        audit_path=tmp_path / "pilot_audit.jsonl",
        fx_conversion_provider=provider,
    )

    governor.write_config(
        {"pilot_enabled": True},
        user_ctx=SUPER_USER,
        confirmation_word="EXECUTE",
    )

    governor.arm(
        user_ctx=SUPER_USER,
        confirmation_word="EXECUTE",
    )

    return governor


def order(amount: str, currency: str):
    return {
        "broker": "OANDA",
        "broker_mode": "live",
        "symbol": "EUR_USD",
        "side": "BUY",
        "notional": amount,
        "notional_currency": currency,
    }


def test_cad_identity_at_exact_limit(tmp_path):
    governor = make_governor(tmp_path)

    decision = governor.evaluate_order(order("20.00", "CAD"))

    assert decision.approved is True
    fx = decision.status["fx_capital_normalization"]
    assert fx["rate"] == 1.0
    assert fx["normalized_notional"] == "20.00"
    assert fx["normalized_currency"] == "CAD"


def test_native_below_20_but_normalized_above_20_blocks(tmp_path):
    governor = make_governor(tmp_path, StaticFXProvider(1.50))

    decision = governor.evaluate_order(order("15.00", "USD"))

    assert decision.approved is False
    assert decision.reason == "max_position_size_breached"


def test_native_above_20_but_normalized_below_20_uses_cad(tmp_path):
    governor = make_governor(tmp_path, StaticFXProvider(0.50))

    decision = governor.evaluate_order(order("30.00", "USD"))

    assert decision.approved is True
    fx = decision.status["fx_capital_normalization"]
    assert fx["native_notional"] == "30.00"
    assert fx["normalized_notional"] == "15.00"


def test_remaining_capacity_uses_normalized_cad(tmp_path):
    governor = make_governor(tmp_path, StaticFXProvider(1.50))

    decision = governor.evaluate_order(
        order("8.00", "USD"),
        open_positions=[
            {
                "symbol": "BTC-USD",
                "side": "BUY",
                "notional": "10.00",
                "notional_currency": "CAD",
            }
        ],
    )

    assert decision.approved is False
    assert decision.reason == "max_live_test_capital_breached"


def test_missing_notional_currency_fails_closed(tmp_path):
    governor = make_governor(tmp_path)

    payload = order("1.00", "CAD")
    del payload["notional_currency"]

    decision = governor.evaluate_order(payload)

    assert decision.approved is False
    assert decision.reason == "live_notional_currency_missing"


def test_unavailable_cross_currency_provider_fails_closed(tmp_path):
    governor = make_governor(tmp_path, UnavailableFXConversionProvider())

    decision = governor.evaluate_order(order("1.00", "USD"))

    assert decision.approved is False
    assert decision.reason == "fx_conversion_unavailable"


def test_record_requires_approved_decision(tmp_path):
    governor = make_governor(tmp_path)

    with pytest.raises(LiveMicroPilotAuthorizationError):
        governor.record_order_submitted(order("1.00", "CAD"))


def test_record_persists_exact_approved_cad_notional(tmp_path):
    governor = make_governor(tmp_path, StaticFXProvider(1.25))

    payload = order("8.00", "USD")
    decision = governor.evaluate_order(payload)

    assert decision.approved is True
    assert decision.status["fx_capital_normalization"]["normalized_notional"] == "10.00"

    status = governor.record_order_submitted(
        payload,
        decision=decision,
    )

    assert status["capital_deployed"] == "10.00"
    assert status["remaining_live_test_capacity"] == "10.00"

    state = governor._load_state()
    position = state["open_positions"][0]

    assert position["notional"] == "10.00"
    assert position["notional_currency"] == "CAD"
    assert position["native_notional"] == "8.00"
    assert position["native_currency"] == "USD"
    assert position["fx_capital_normalization"]["normalized_notional"] == "10.00"


def test_second_order_sees_persisted_cad_exposure(tmp_path):
    governor = make_governor(tmp_path, StaticFXProvider(1.25))

    first = order("8.00", "USD")
    first_decision = governor.evaluate_order(first)

    assert first_decision.approved is True

    governor.record_order_submitted(
        first,
        decision=first_decision,
    )

    # Stored exposure is CAD 10.00. A second USD 9.00 becomes
    # CAD 11.25 and therefore exceeds remaining CAD 10.00.
    second = order("9.00", "USD")
    second["symbol"] = "GBP_USD"

    second_decision = governor.evaluate_order(second)

    assert second_decision.approved is False
    assert second_decision.reason == "max_live_test_capital_breached"
