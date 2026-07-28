import pytest

from backend.analytics.trade_outcome_repository import DuplicateTradeOutcomeError, TradeOutcomeRepository
from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycle, CanonicalTradeLifecycleError


@pytest.fixture
def repo(tmp_path):
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()
    return repository


@pytest.fixture
def lifecycle(repo):
    return CanonicalTradeLifecycle(repo)


def _close_payload(trade_id="t1", symbol="EUR_USD", asset_class="FX", broker="OANDA"):
    return {
        "trade_id": trade_id,
        "timestamp_open": "2026-06-24T10:00:00+00:00",
        "timestamp_close": "2026-06-24T10:05:00+00:00",
        "symbol": symbol,
        "asset_class": asset_class,
        "entry_price": 1.1050,
        "exit_price": 1.1080,
        "quantity": 10000.0,
        "realized_pnl": 30.0,
        "holding_duration_seconds": 300.0,
        "strategy_id": "mean_reversion",
        "market_regime": "risk_on",
        "broker": broker,
    }


@pytest.mark.parametrize(
    ("asset_class", "symbol", "broker"),
    [
        ("FX", "EUR_USD", "OANDA"),
        ("crypto", "BTC_USD", "COINBASE"),
        ("options", "SPY-C-250", "SIM"),
        ("futures", "ES", "SIM"),
    ],
)
def test_close_outcome_persistence_across_asset_classes(lifecycle, asset_class, symbol, broker):
    payload = _close_payload(trade_id=f"{asset_class.lower()}-trade", symbol=symbol, asset_class=asset_class, broker=broker)

    persisted = lifecycle.persist_closed_trade_outcome(payload)

    assert persisted["trade_id"] == f"{asset_class.lower()}-trade"
    expected_asset_class = {
        "fx": "FX",
        "crypto": "CRYPTO",
        "options": "OPTIONS",
        "futures": "FUTURES",
    }[asset_class.lower()]
    assert persisted["asset_class"] == expected_asset_class
    assert persisted["symbol"] == symbol
    assert persisted["broker"] == broker
    assert persisted["realized_pnl"] == 30.0


def test_missing_realized_pnl_fails_closed(lifecycle):
    payload = _close_payload()
    payload.pop("realized_pnl")

    with pytest.raises(CanonicalTradeLifecycleError):
        lifecycle.persist_closed_trade_outcome(payload)


def test_missing_timestamp_fails_closed(lifecycle):
    payload = _close_payload()
    payload.pop("timestamp_close")

    with pytest.raises(CanonicalTradeLifecycleError):
        lifecycle.persist_closed_trade_outcome(payload)


def test_unsupported_asset_class_fails_closed(lifecycle):
    payload = _close_payload(asset_class="commodity")

    with pytest.raises(CanonicalTradeLifecycleError):
        lifecycle.persist_closed_trade_outcome(payload)


def test_duplicate_trade_id_fails_closed_through_repository(lifecycle):
    payload = _close_payload(trade_id="dup-trade")

    lifecycle.persist_closed_trade_outcome(payload)

    with pytest.raises(CanonicalTradeLifecycleError):
        lifecycle.persist_closed_trade_outcome(payload)
