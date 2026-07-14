from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.config.order_limit_config import (
    CanonicalOrderLimitConfig,
    DEFAULT_ORDER_LIMIT_CONFIG,
    OrderLimitConfigurationError,
)
from backend.options.options_paper_broker import OptionsPaperBroker
from backend.trading.option_contract import CanonicalOptionContract
from backend.runtime.live_micro_pilot_governor import (
    LiveMicroPilotConfig,
    LiveMicroPilotConfigurationError,
)
import dashboard.mobile.mobile_app as mobile_app


AS_OF = date(2026, 7, 14)
EXPIRY = (AS_OF + timedelta(days=30)).isoformat()
NOW = "2026-07-14T00:00:00+00:00"


def _contract() -> CanonicalOptionContract:
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": "SPY",
            "option_symbol": f"SPY-{EXPIRY}-C-105",
            "expiration_date": EXPIRY,
            "strike": 105.0,
            "option_type": "CALL",
            "bid": 1.9,
            "ask": 2.1,
            "midpoint": 2.0,
            "last": 2.0,
            "volume": 250,
            "open_interest": 800,
            "implied_volatility": 0.22,
            "delta": 0.30,
            "gamma": 0.02,
            "theta": -0.01,
            "vega": 0.10,
            "rho": 0.01,
            "intrinsic_value": 0.0,
            "extrinsic_value": 2.0,
            "probability_itm": 0.30,
            "exchange": "CBOE",
            "multiplier": 100,
            "currency": "USD",
            "timestamp": NOW,
        }
    )


def test_missing_order_limit_config_defaults_to_safest_live_limit() -> None:
    config = CanonicalOrderLimitConfig.from_mapping({})

    assert config.live_order_default_notional_usd == Decimal("1.00")
    assert config.live_pilot_max_total_cad == Decimal("20.00")
    assert config.live_pilot_max_position_cad == Decimal("20.00")
    assert config.live_pilot_max_concurrent_positions == 1
    payload = config.to_dict()
    assert payload["execution_allowed"] is False
    assert payload["live_trading_blocked"] is True
    assert payload["broker_execution_armed"] is False


def test_paper_mode_limits_can_be_configured_independently() -> None:
    config = CanonicalOrderLimitConfig.from_mapping(
        {
            "paper_order_default_notional_usd": "25000.00",
            "paper_order_max_notional_usd": "50000.00",
        }
    )

    assert config.paper_order_default_notional_usd == Decimal("25000.00")
    assert config.paper_order_max_notional_usd == Decimal("50000.00")
    assert config.live_order_default_notional_usd == Decimal("1.00")
    assert config.live_pilot_max_total_cad == Decimal("20.00")


def test_preview_can_model_higher_hypothetical_amount_without_execution_authority() -> None:
    config = CanonicalOrderLimitConfig.from_mapping(
        {"preview_max_hypothetical_notional_usd": "250000.00"}
    )
    broker = OptionsPaperBroker(contracts=[_contract()], buying_power=500000.0)

    preview = broker.preview_order(
        strategy="COVERED_CALL",
        collateral=float(config.preview_max_hypothetical_notional_usd / Decimal("2")),
        premium=1000.0,
        quantity=2,
        option_symbol=f"SPY-{EXPIRY}-C-105",
    )

    assert preview["estimated_collateral"] == 250000.0
    assert preview["preview_status"] == "PASS"
    assert preview["execution_allowed"] is False
    assert preview["live_trading_blocked"] is True
    assert preview["broker_execution_armed"] is False
    assert "order_id" not in preview


@pytest.mark.parametrize(
    "payload",
    [
        {"live_order_default_notional_usd": "1.01"},
        {"live_pilot_max_total_cad": "20.01"},
        {"live_pilot_max_position_cad": "20.01"},
        {"live_pilot_max_concurrent_positions": 2},
        {"paper_order_default_notional_usd": "-1.00"},
        {"paper_order_default_notional_usd": "NaN"},
        {"paper_order_max_notional_usd": "1000000.01"},
        {"preview_max_hypothetical_notional_usd": "10000000.01"},
    ],
)
def test_invalid_negative_non_finite_or_excessive_limits_fail_closed(payload) -> None:
    with pytest.raises(OrderLimitConfigurationError):
        CanonicalOrderLimitConfig.from_mapping(payload)


def test_live_micro_pilot_consumes_canonical_limits_without_raising_capacity() -> None:
    config = LiveMicroPilotConfig()

    assert config.max_live_test_capital == DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_total_cad
    assert config.max_position_size == DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad
    assert config.max_concurrent_positions == DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_concurrent_positions
    assert config.max_orders_per_session == DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_orders_per_session
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"max_concurrent_positions": 2})


def test_mobile_controls_cannot_override_live_limits(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")

    saved = mobile_app.save_mobile_controls(
        {
            "mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED",
            "engine_mode": "BALANCED",
            "live_order_kill_switch": False,
            "live_order_default_notional_usd": "999.00",
            "max_live_test_capital": "999.00",
            "max_position_size": "999.00",
        }
    )
    loaded = mobile_app.load_mobile_controls()

    assert "live_order_default_notional_usd" not in saved
    assert "max_live_test_capital" not in saved
    assert "max_position_size" not in loaded
    assert mobile_app.DEFAULT_COINBASE_MAX_LIVE_ORDER_USD == 1.0
