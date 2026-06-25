from __future__ import annotations

import pytest

from backend.trading.instrument_universe import InstrumentUniverse, InstrumentUniverseError, TradableInstrument


def test_registry_returns_instruments() -> None:
    universe = InstrumentUniverse()
    all_rows = universe.all_instruments()

    assert isinstance(all_rows, list)
    assert len(all_rows) > 0
    assert all("symbol" in row for row in all_rows)


def test_filters_by_asset_class() -> None:
    universe = InstrumentUniverse()

    fx_rows = universe.instruments_by_asset_class("FX")
    assert fx_rows
    assert all(row["asset_class"] == "FX" for row in fx_rows)


def test_filters_by_broker() -> None:
    universe = InstrumentUniverse()

    rows = universe.instruments_by_broker("coinbase")
    assert rows
    assert all(row["broker"] == "coinbase" for row in rows)


def test_paper_supported_tradable_subset() -> None:
    universe = InstrumentUniverse()

    rows = universe.tradable_paper_instruments()
    assert rows
    assert all(row["paper_supported"] is True for row in rows)
    assert all(row["tradable"] is True for row in rows)


def test_invalid_asset_class_fails_closed() -> None:
    universe = InstrumentUniverse()

    with pytest.raises(InstrumentUniverseError):
        universe.instruments_by_asset_class("BONDS")


def test_fail_closed_fallback_when_discovery_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    universe = InstrumentUniverse()

    def _boom(*args, **kwargs):
        raise RuntimeError("discovery failed")

    monkeypatch.setattr(universe, "_discover_option_contracts", _boom)
    universe.refresh()

    rows = universe.all_instruments()
    assert rows
    assert all(row["status"] == "DISCOVERY_FALLBACK" for row in rows)
    assert all(row["tradable"] is False for row in rows)


def test_feed_contains_all_required_views() -> None:
    universe = InstrumentUniverse()
    feed = universe.build_feed()

    assert "all_instruments" in feed
    assert "instruments_by_asset_class" in feed
    assert "instruments_by_broker" in feed
    assert "tradable_paper_instruments" in feed


def test_universe_can_include_non_tradeable_entries() -> None:
    universe = InstrumentUniverse()
    all_rows = universe.all_instruments()

    assert any(bool(row.get("tradable")) is False for row in all_rows)


def test_tradeable_symbols_paper_excludes_non_tradeable_and_live_only() -> None:
    universe = InstrumentUniverse()
    now = "2026-06-25T00:00:00Z"
    universe._instruments = [
        TradableInstrument(
            symbol="PAPER_OK",
            display_name="Paper OK",
            asset_class="FX",
            broker="oanda",
            tradable=True,
            paper_supported=True,
            live_supported=False,
            exchange="OANDA",
            currency="USD",
            min_order_size=1.0,
            max_order_size=1000.0,
            tick_size=0.0001,
            last_updated=now,
            status="ACTIVE",
            metadata={},
        ),
        TradableInstrument(
            symbol="NON_TRADEABLE",
            display_name="Non Tradeable",
            asset_class="FX",
            broker="oanda",
            tradable=False,
            paper_supported=True,
            live_supported=False,
            exchange="OANDA",
            currency="USD",
            min_order_size=1.0,
            max_order_size=1000.0,
            tick_size=0.0001,
            last_updated=now,
            status="ACTIVE",
            metadata={},
        ),
        TradableInstrument(
            symbol="LIVE_ONLY",
            display_name="Live Only",
            asset_class="CRYPTO",
            broker="coinbase",
            tradable=True,
            paper_supported=False,
            live_supported=True,
            exchange="COINBASE",
            currency="USD",
            min_order_size=0.001,
            max_order_size=1000.0,
            tick_size=0.01,
            last_updated=now,
            status="ACTIVE",
            metadata={},
        ),
        TradableInstrument(
            symbol="FAIL_CLOSED",
            display_name="Fail Closed",
            asset_class="FX",
            broker="oanda",
            tradable=True,
            paper_supported=True,
            live_supported=True,
            exchange="OANDA",
            currency="USD",
            min_order_size=1.0,
            max_order_size=1000.0,
            tick_size=0.0001,
            last_updated=now,
            status="ACTIVE",
            metadata={"fail_closed": True},
        ),
        TradableInstrument(
            symbol="PAPER_ACTIVE_OK",
            display_name="Paper Active",
            asset_class="FX",
            broker="oanda",
            tradable=True,
            paper_supported=True,
            live_supported=False,
            exchange="OANDA",
            currency="USD",
            min_order_size=1.0,
            max_order_size=1000.0,
            tick_size=0.0001,
            last_updated=now,
            status="PAPER_ACTIVE",
            metadata={},
        ),
    ]

    rows = universe.tradeable_symbols(mode="paper")
    symbols = {row.symbol for row in rows}

    assert "PAPER_OK" in symbols
    assert "PAPER_ACTIVE_OK" in symbols
    assert "NON_TRADEABLE" not in symbols
    assert "LIVE_ONLY" not in symbols
    assert "FAIL_CLOSED" not in symbols
