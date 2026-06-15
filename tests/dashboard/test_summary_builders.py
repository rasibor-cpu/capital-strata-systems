from __future__ import annotations

from decimal import Decimal

from dashboard.runtime.state_builders.position_state_builder import PositionStateBuilder
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder
from engine.ledger import CANONICAL_PNL_SOURCE
from engine.ledger.pnl_snapshot_adapter import CanonicalPnLSnapshotContract


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
        "realized_pnl": 5.0,
        "unrealized_pnl": 12.5,
        "equity": 1000.0,
        "total_exposure": 250.0,
        "winner_count": 3,
        "loser_count": 1,
        "asset_realized_pnl": {"CRYPTO": 5.0},
        "asset_unrealized_pnl": {"CRYPTO": 12.5},
        "source": "LEGACY_POSITION_STATE",
    }
    summary = PnLSummaryBuilder().build(
        account_state={"equity": 1000.0},
        position_state=position_state,
    )

    assert set(summary) == {
        "realized_pnl",
        "unrealized_pnl",
        "net_pnl",
        "equity",
        "peak_equity",
        "current_drawdown",
        "max_drawdown",
        "total_exposure",
        "exposure_utilization_pct",
        "winner_count",
        "loser_count",
        "win_rate_pct",
        "asset_realized_pnl",
        "asset_unrealized_pnl",
        "open_positions",
        "closed_positions",
        "source",
        "account_equity",
    }
    assert summary["realized_pnl"] == 5.0
    assert summary["unrealized_pnl"] == 12.5
    assert summary["net_pnl"] == 17.5
    assert summary["equity"] == 1000.0
    assert summary["peak_equity"] == 1000.0
    assert summary["current_drawdown"] == 0.0
    assert summary["max_drawdown"] == 0.0
    assert summary["exposure_utilization_pct"] == 25.0
    assert summary["win_rate_pct"] == 75.0
    assert summary["asset_realized_pnl"] == {"CRYPTO": 5.0}
    assert summary["asset_unrealized_pnl"] == {"CRYPTO": 12.5}
    assert summary["open_positions"] == 0
    assert summary["closed_positions"] == 0
    assert summary["source"] == "LEGACY_POSITION_STATE"


def test_pnl_summary_builder_consumes_canonical_adapter_output() -> None:
    canonical_output = CanonicalPnLSnapshotContract(
        realized_pnl=Decimal("15.25"),
        unrealized_pnl=Decimal("-2.50"),
        net_pnl=Decimal("12.75"),
        equity=Decimal("1012.75"),
        peak_equity=Decimal("1050.00"),
        current_drawdown=Decimal("0.035476190476190476"),
        max_drawdown=Decimal("0.0500"),
        asset_realized_pnl={
            "CRYPTO": Decimal("10.25"),
            "FX": Decimal("5.00"),
        },
        asset_unrealized_pnl={
            "CRYPTO": Decimal("-1.00"),
            "FX": Decimal("-1.50"),
        },
        open_positions=2,
        closed_positions=1,
        source=CANONICAL_PNL_SOURCE,
    ).to_runtime_dict()

    summary = PnLSummaryBuilder().build(
        account_state={"equity": 999.0},
        position_state=canonical_output,
    )

    assert summary["realized_pnl"] == 15.25
    assert summary["unrealized_pnl"] == -2.5
    assert summary["net_pnl"] == 12.75
    assert summary["equity"] == 1012.75
    assert summary["account_equity"] == 1012.75
    assert summary["peak_equity"] == 1050.0
    assert summary["current_drawdown"] == 0.035476190476190476
    assert summary["max_drawdown"] == 0.05
    assert summary["asset_realized_pnl"] == {
        "CRYPTO": 10.25,
        "FX": 5.0,
    }
    assert summary["asset_unrealized_pnl"] == {
        "CRYPTO": -1.0,
        "FX": -1.5,
    }
    assert summary["open_positions"] == 2
    assert summary["closed_positions"] == 1
    assert summary["source"] == CANONICAL_PNL_SOURCE


def test_pnl_summary_builder_safely_handles_invalid_asset_maps() -> None:
    summary = PnLSummaryBuilder().build(
        account_state={},
        position_state={
            "realized_pnl": "3.5",
            "unrealized_pnl": "4.5",
            "asset_realized_pnl": ["not", "a", "map"],
            "asset_unrealized_pnl": {"CRYPTO": "bad-value"},
            "source": CANONICAL_PNL_SOURCE,
        },
    )

    assert summary["realized_pnl"] == 3.5
    assert summary["unrealized_pnl"] == 4.5
    assert summary["net_pnl"] == 8.0
    assert summary["asset_realized_pnl"] == {}
    assert summary["asset_unrealized_pnl"] == {"CRYPTO": 0.0}
    assert summary["source"] == CANONICAL_PNL_SOURCE

