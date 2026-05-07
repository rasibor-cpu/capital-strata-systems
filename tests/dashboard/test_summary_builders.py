from __future__ import annotations

from dashboard.runtime.state_builders.position_state_builder import PositionStateBuilder
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder


def test_position_builder_handles_empty_payload() -> None:
    state = PositionStateBuilder().build({})

    assert state["positions"] == []
    assert state["open_count"] == 0
    assert state["total_exposure"] == 0.0
    assert state["total_realized_pnl"] == 0.0
    assert state["total_unrealized_pnl"] == 0.0
    assert state["net_pnl"] == 0.0


def test_position_builder_aggregates_realized_and_unrealized_pnl() -> None:
    state = PositionStateBuilder().build(
        {
            "positions": [
                {
                    "symbol": "BTC-USD",
                    "asset_class": "crypto",
                    "side": "long",
                    "qty": "2",
                    "entry_price": "100",
                    "current_price": "125",
                    "realized_pnl": "7.50",
                    "unrealized_pnl": "50",
                },
                {
                    "symbol": "EUR_USD",
                    "asset_class": "fx",
                    "side": "short",
                    "qty": 1000,
                    "entry_price": 1.1,
                    "current_price": 1.09,
                    "realized_pnl": -2.5,
                    "unrealized_pnl": 3.25,
                },
            ]
        }
    )

    assert state["open_count"] == 2
    assert state["asset_counts"] == {"CRYPTO": 1, "FX": 1}
    assert state["long_count"] == 1
    assert state["short_count"] == 1
    assert state["winner_count"] == 2
    assert state["loser_count"] == 0
    assert state["total_realized_pnl"] == 5.0
    assert state["total_unrealized_pnl"] == 53.25
    assert state["net_pnl"] == 58.25


def test_position_builder_defaults_missing_pnl_fields_to_zero() -> None:
    state = PositionStateBuilder().build(
        {
            "positions": [
                {
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "side": "buy",
                    "quantity": "3",
                    "entry": "10",
                    "mark_price": "12",
                }
            ]
        }
    )

    assert state["open_count"] == 1
    assert state["total_exposure"] == 36.0
    assert state["total_realized_pnl"] == 0.0
    assert state["total_unrealized_pnl"] == 0.0
    assert state["asset_realized_pnl"] == {"EQUITY": 0.0}
    assert state["asset_unrealized_pnl"] == {"EQUITY": 0.0}


def test_pnl_summary_builder_shape_and_totals_are_stable() -> None:
    position_state = {
        "total_realized_pnl": 5.0,
        "total_unrealized_pnl": 12.5,
        "total_exposure": 250.0,
        "winner_count": 3,
        "loser_count": 1,
        "asset_realized_pnl": {"CRYPTO": 5.0},
        "asset_unrealized_pnl": {"CRYPTO": 12.5},
    }
    summary = PnLSummaryBuilder().build(
        account_state={"equity": 1000.0},
        position_state=position_state,
    )

    assert set(summary) == {
        "realized_pnl",
        "unrealized_pnl",
        "net_pnl",
        "total_exposure",
        "exposure_utilization_pct",
        "winner_count",
        "loser_count",
        "win_rate_pct",
        "asset_realized_pnl",
        "asset_unrealized_pnl",
        "account_equity",
    }
    assert summary["realized_pnl"] == 5.0
    assert summary["unrealized_pnl"] == 12.5
    assert summary["net_pnl"] == 17.5
    assert summary["exposure_utilization_pct"] == 25.0
    assert summary["win_rate_pct"] == 75.0

