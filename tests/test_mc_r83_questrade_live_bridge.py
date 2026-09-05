from datetime import datetime, timezone

from backend.brokers.questrade.contracts import map_positions
from backend.runtime.canonical_broker_portfolio import build_canonical_broker_portfolio


def test_r83_open_quantity_maps_to_quantity_and_preserves_open_pnl():
    mapped = map_positions({"positions": [{"symbol": "TD", "openQuantity": 5, "currentMarketValue": 608.15, "openPnl": 311.8525}]}, generated_at="2026-09-05T01:35:00+00:00")
    row = mapped["holdings"][0]
    assert row["quantity"] == 5
    assert row["market_value"] == 608.15
    assert row["unrealized_pnl"] == 311.8525


def test_r83_live_raw_payload_uses_acquisition_timestamp_and_counts_equities():
    ts = "2026-09-05T01:35:00+00:00"
    raw = {"selected_broker": "QUESTRADE", "canonical_mode": "LIVE_READ_ONLY", "questrade": {"status": "AVAILABLE", "balances": {"acquisition_timestamp": ts, "combinedBalances": [{"currency": "CAD", "cash": -95.0, "marketValue": 1680.0, "totalEquity": 1585.0, "buyingPower": 3597.0}]}, "positions": {"acquisition_timestamp": ts, "positions": [{"symbol": "TD", "openQuantity": 5, "currentMarketValue": 608.15, "openPnl": 311.8525}, {"symbol": "T.TO", "openQuantity": 10, "currentMarketValue": 133.9, "openPnl": -107.0}, {"symbol": "ENB", "openQuantity": 10, "currentMarketValue": 503.0, "openPnl": 166.109}]}}}
    portfolio = build_canonical_broker_portfolio(raw, now=datetime(2026, 9, 5, 1, 35, 30, tzinfo=timezone.utc))
    assert portfolio["status"] == "AVAILABLE"
    assert portfolio["metrics"]["open_positions"]["value"] == 0
    assert len(portfolio["exposures"]) == 3
    assert all(row["exposure_kind"] == "HOLDING" for row in portfolio["exposures"])
    assert [row["quantity"] for row in portfolio["exposures"]] == [5, 10, 10]
    assert [row["unrealized_pnl"] for row in portfolio["exposures"]] == [311.8525, -107.0, 166.109]
    assert all(row["unrealized_pnl_availability"] == "AVAILABLE" for row in portfolio["exposures"])
    assert portfolio["metrics"]["session_pnl"]["availability"] == "UNAVAILABLE"
    assert portfolio["metrics"]["realized_pnl"]["availability"] == "UNAVAILABLE"
    assert portfolio["metrics"]["unrealized_pnl"]["availability"] == "UNAVAILABLE"
    assert portfolio["execution_allowed"] is False
    assert portfolio["live_trading_blocked"] is True
    assert portfolio["broker_execution_armed"] is False
    assert portfolio["advisory_only"] is True
