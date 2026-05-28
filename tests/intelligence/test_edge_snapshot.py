from backend.intelligence.edge_validation.edge_snapshot import (
    build_edge_snapshot,
)


def test_edge_snapshot_empty_input_is_safe():

    snapshot = build_edge_snapshot([])

    assert snapshot["trade_count"] == 0.0
    assert snapshot["gross_pnl"] == 0.0
    assert snapshot["total_costs"] == 0.0
    assert snapshot["net_pnl"] == 0.0
    assert snapshot["expectancy"] == 0.0


def test_edge_snapshot_exposes_core_metrics():

    trades = [
        {
            "gross_pnl": 1000,
            "costs": 100,
        },
        {
            "gross_pnl": -200,
            "costs": 25,
        },
    ]

    snapshot = build_edge_snapshot(trades)

    assert snapshot["trade_count"] == 2.0
    assert snapshot["gross_pnl"] == 800.0
    assert snapshot["total_costs"] == 125.0
    assert snapshot["net_pnl"] == 675.0
    assert "expectancy" in snapshot
    assert "profit_factor" in snapshot
    assert "win_rate" in snapshot


def test_edge_snapshot_does_not_mutate_trade_input():

    trades = [
        {
            "gross_pnl": 500,
            "costs": 50,
        }
    ]

    original = list(trades)

    build_edge_snapshot(trades)

    assert trades == original