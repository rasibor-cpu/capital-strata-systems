from backend.intelligence.edge_validation.edge_metrics import (
    compute_edge_metrics,
)


def test_empty_input_returns_zero_metrics():

    metrics = compute_edge_metrics([])

    assert (
        metrics["trade_count"]
        == 0.0
    )

    assert (
        metrics["gross_pnl"]
        == 0.0
    )

    assert (
        metrics["net_pnl"]
        == 0.0
    )

    assert (
        metrics["expectancy"]
        == 0.0
    )


def test_profitable_sample_returns_positive_metrics():

    trades = [
        {
            "gross_pnl": 1000,
            "costs": 100,
        },
        {
            "gross_pnl": 500,
            "costs": 50,
        },
    ]

    metrics = compute_edge_metrics(
        trades
    )

    assert (
        metrics["gross_pnl"]
        == 1500.0
    )

    assert (
        metrics["total_costs"]
        == 150.0
    )

    assert (
        metrics["net_pnl"]
        == 1350.0
    )

    assert (
        metrics["expectancy"]
        > 0.0
    )

    assert (
        metrics["win_rate"]
        == 1.0
    )


def test_losing_sample_returns_negative_expectancy():

    trades = [
        {
            "gross_pnl": -500,
            "costs": 50,
        },
        {
            "gross_pnl": -300,
            "costs": 50,
        },
    ]

    metrics = compute_edge_metrics(
        trades
    )

    assert (
        metrics["net_pnl"]
        < 0.0
    )

    assert (
        metrics["expectancy"]
        < 0.0
    )


def test_cost_drag_can_turn_profit_into_loss():

    trades = [
        {
            "gross_pnl": 100,
            "costs": 150,
        }
    ]

    metrics = compute_edge_metrics(
        trades
    )

    assert (
        metrics["gross_pnl"]
        == 100.0
    )

    assert (
        metrics["net_pnl"]
        == -50.0
    )


def test_profit_factor_handles_zero_losses():

    trades = [
        {
            "gross_pnl": 1000,
            "costs": 0,
        }
    ]

    metrics = compute_edge_metrics(
        trades
    )

    assert (
        metrics["profit_factor"]
        > 0.0
    )


def test_missing_cost_fields_do_not_crash():

    trades = [
        {
            "gross_pnl": 500,
        }
    ]

    metrics = compute_edge_metrics(
        trades
    )

    assert (
        metrics["net_pnl"]
        == 500.0
    )
