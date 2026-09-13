from decimal import Decimal

import pytest

from backend.data.price_feed import PriceFeed


def test_price_feed_is_network_disabled_and_fail_closed(monkeypatch):
    monkeypatch.setenv("DATA_PROVIDER", "UNAVAILABLE")
    monkeypatch.delenv("CSS_TEST_MODE", raising=False)
    feed = PriceFeed()

    assert feed.live_network_enabled is False
    assert feed.get_price("EUR_USD") is None


def test_simulated_price_can_be_injected_in_test_mode(monkeypatch):
    monkeypatch.setenv("CSS_TEST_MODE", "1")
    feed = PriceFeed(provider="SIMULATED")
    feed.set_simulated_price("EUR_USD", Decimal("1.0500"))

    assert feed.get_price("eur_usd") == 1.05


def test_nonpositive_simulated_price_is_rejected(monkeypatch):
    monkeypatch.setenv("CSS_TEST_MODE", "1")
    feed = PriceFeed(provider="SIMULATED")

    with pytest.raises(ValueError, match="positive"):
        feed.set_simulated_price("EUR_USD", "0")


def test_no_live_provider_surface_is_introduced():
    prohibited = {
        "place_order",
        "submit_order",
        "cancel_order",
        "withdraw",
        "transfer",
        "deposit",
        "fund_account",
        "move_money",
    }
    assert prohibited.isdisjoint(set(dir(PriceFeed)))
