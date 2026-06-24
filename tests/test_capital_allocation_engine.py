import pytest

from backend.analytics import CapitalAllocationEngine, CapitalAllocationEngineError


def test_preferred_symbol_allocation():
    engine = CapitalAllocationEngine()
    ranking = [
        {"symbol": "AAPL", "score": 10.0, "trade_count": 5, "realized_pnl": 100.0},
        {"symbol": "MSFT", "score": 1.0, "trade_count": 5, "realized_pnl": 10.0},
    ]

    allocations = engine.allocate(
        ranking,
        available_capital=1000.0,
        max_symbol_weight=0.6,
        min_trade_count=3,
        restricted_score_threshold=0.0,
    )

    assert [row["symbol"] for row in allocations] == ["AAPL", "MSFT"]
    assert allocations[0]["status"] == "PREFERRED"
    assert allocations[0]["allocation_weight"] == pytest.approx(0.6)
    assert allocations[0]["allocation_amount"] == pytest.approx(600.0)
    assert allocations[1]["allocation_weight"] == pytest.approx(0.4)
    assert allocations[1]["allocation_amount"] == pytest.approx(400.0)


def test_neutral_symbol_behavior():
    engine = CapitalAllocationEngine()
    ranking = [
        {"symbol": "AAPL", "score": 0.0, "trade_count": 5, "realized_pnl": 0.0},
        {"symbol": "MSFT", "score": 5.0, "trade_count": 5, "realized_pnl": 50.0},
    ]

    allocations = engine.allocate(
        ranking,
        available_capital=1000.0,
        max_symbol_weight=1.0,
        min_trade_count=3,
        restricted_score_threshold=0.0,
    )
    aapl = next(row for row in allocations if row["symbol"] == "AAPL")

    assert aapl["status"] == "NEUTRAL"
    assert aapl["allocation_weight"] == pytest.approx(0.0)
    assert aapl["allocation_amount"] == pytest.approx(0.0)


def test_restricted_symbols_receive_zero_allocation():
    engine = CapitalAllocationEngine()
    ranking = [
        {"symbol": "AAPL", "score": 10.0, "trade_count": 5, "realized_pnl": 100.0},
        {"symbol": "MSFT", "score": 1.0, "trade_count": 1, "realized_pnl": 10.0},
    ]

    allocations = engine.allocate(
        ranking,
        available_capital=1000.0,
        max_symbol_weight=1.0,
        min_trade_count=3,
        restricted_score_threshold=0.0,
    )
    msft = next(row for row in allocations if row["symbol"] == "MSFT")

    assert msft["status"] == "RESTRICTED"
    assert msft["allocation_weight"] == pytest.approx(0.0)
    assert msft["allocation_amount"] == pytest.approx(0.0)


def test_total_weight_cap():
    engine = CapitalAllocationEngine()
    ranking = [
        {"symbol": "AAPL", "score": 10.0, "trade_count": 5, "realized_pnl": 100.0},
        {"symbol": "MSFT", "score": 10.0, "trade_count": 5, "realized_pnl": 100.0},
        {"symbol": "EURUSD", "score": 10.0, "trade_count": 5, "realized_pnl": 100.0},
    ]

    allocations = engine.allocate(
        ranking,
        available_capital=1000.0,
        max_symbol_weight=0.5,
        min_trade_count=3,
        restricted_score_threshold=0.0,
    )

    assert sum(row["allocation_weight"] for row in allocations) == pytest.approx(1.0)


def test_max_symbol_weight_cap():
    engine = CapitalAllocationEngine()
    ranking = [
        {"symbol": "AAPL", "score": 100.0, "trade_count": 5, "realized_pnl": 1000.0},
        {"symbol": "MSFT", "score": 1.0, "trade_count": 5, "realized_pnl": 10.0},
    ]

    allocations = engine.allocate(
        ranking,
        available_capital=1000.0,
        max_symbol_weight=0.4,
        min_trade_count=3,
        restricted_score_threshold=0.0,
    )

    assert max(row["allocation_weight"] for row in allocations) <= 0.4 + 1e-9


def test_empty_ranking_behavior():
    engine = CapitalAllocationEngine()

    assert engine.allocate([], available_capital=1000.0, max_symbol_weight=0.5, min_trade_count=3, restricted_score_threshold=0.0) == []


def test_invalid_capital_fail_closed():
    engine = CapitalAllocationEngine()

    with pytest.raises(CapitalAllocationEngineError):
        engine.allocate(
            [{"symbol": "AAPL", "score": 1.0, "trade_count": 3, "realized_pnl": 10.0}],
            available_capital=0.0,
            max_symbol_weight=0.5,
            min_trade_count=3,
            restricted_score_threshold=0.0,
        )


def test_invalid_max_weight_fail_closed():
    engine = CapitalAllocationEngine()

    with pytest.raises(CapitalAllocationEngineError):
        engine.allocate(
            [{"symbol": "AAPL", "score": 1.0, "trade_count": 3, "realized_pnl": 10.0}],
            available_capital=1000.0,
            max_symbol_weight=1.1,
            min_trade_count=3,
            restricted_score_threshold=0.0,
        )
