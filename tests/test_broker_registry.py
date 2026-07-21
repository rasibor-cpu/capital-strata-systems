import pytest

from backend.app.brokers.broker_registry import (
    BROKER_REGISTRY,
    get_adapter,
    get_broker_spec,
    list_supported_brokers,
)
from backend.app.brokers.oanda_adapter import OandaAdapter
from backend.app.brokers.operational_adapter import (
    BinanceOperationalAdapter,
    QuestradeOperationalAdapter,
)
from backend.broker.coinbase_adapter import CoinbaseAdapter


def test_registry_contains_approved_brokers() -> None:
    brokers = list_supported_brokers()
    assert "oanda" in brokers
    assert "coinbase" in brokers
    assert "binance" in brokers
    assert "questrade" in brokers
    assert "alpaca" not in brokers


def test_get_broker_spec_for_unregistered_broker_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="Unsupported broker 'ibkr'"):
        get_broker_spec("ibkr")


def test_get_adapter_resolves_canonical_brokers() -> None:
    assert get_adapter("oanda") == OandaAdapter
    assert get_adapter("coinbase") == CoinbaseAdapter


def test_get_adapter_returns_structured_state_adapters() -> None:
    assert get_adapter("binance") is BinanceOperationalAdapter
    assert get_adapter("questrade") is QuestradeOperationalAdapter
    assert BinanceOperationalAdapter().readiness()["state"] == "CREDENTIALS_REQUIRED"
    assert QuestradeOperationalAdapter().readiness()["state"] == "CONFIGURATION_REQUIRED"


def test_get_adapter_for_unregistered_broker_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="Unsupported broker"):
        get_adapter("unknown_broker")
