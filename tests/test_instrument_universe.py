from __future__ import annotations

import pytest

from backend.trading.instrument_universe import InstrumentUniverse, InstrumentUniverseError


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
