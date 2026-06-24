from __future__ import annotations

import pytest

from backend.analytics.trade_outcome_repository import TradeOutcomeRepository, build_trade_outcome_analytics_adapter
from backend.app.futures.futures_lifecycle_adapter import FuturesLifecycleAdapter
from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycleError


@pytest.fixture
def repo(tmp_path):
    repository = TradeOutcomeRepository(tmp_path / "futures_outcomes.json")
    repository.create_storage()
    return repository


@pytest.fixture
def adapter(repo):
    return FuturesLifecycleAdapter(repository=repo)


def test_futures_open_and_close_normalization(adapter):
    open_payload = adapter.build_open_payload(
        trade_id="fut-001",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="ES",
        entry_price=4200.0,
        exit_price=4210.0,
        quantity=1.0,
        strategy_id="futures_mean_reversion",
        market_regime="risk_on",
        broker="SIM",
    )

    normalized_open = adapter.normalize_open_result(open_payload)
    assert normalized_open["asset_class"] == "FUTURES"
    assert normalized_open["symbol"] == "ES"
    assert normalized_open["broker"] == "SIM"

    close_payload = adapter.build_close_payload(
        trade_id="fut-001",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="ES",
        entry_price=4200.0,
        exit_price=4210.0,
        quantity=1.0,
        realized_pnl=10.0,
        strategy_id="futures_mean_reversion",
        market_regime="risk_on",
        broker="SIM",
    )

    normalized_close = adapter.normalize_close_result(close_payload)
    assert normalized_close["asset_class"] == "FUTURES"
    assert normalized_close["realized_pnl"] == 10.0


def test_futures_paper_mode_and_warehouse_persistence(adapter):
    paper_result = adapter.execute_paper_order(
        symbol="ES",
        side="BUY",
        contracts=1,
        mode="paper",
    )
    assert paper_result["approved"] is True
    assert paper_result["dry_run"] is True

    close_payload = adapter.build_close_payload(
        trade_id="fut-warehouse",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="ES",
        entry_price=4200.0,
        exit_price=4210.0,
        quantity=1.0,
        realized_pnl=10.0,
        strategy_id="futures_mean_reversion",
        market_regime="risk_on",
        broker="SIM",
    )

    persisted = adapter.persist_closed_trade_outcome(close_payload)
    assert persisted["trade_id"] == "fut-warehouse"

    analytics = build_trade_outcome_analytics_adapter(adapter.repository)
    assert analytics["top_asset_classes"][0]["asset_class"] == "FUTURES"


def test_futures_duplicate_prevention_and_fail_closed(adapter):
    close_payload = adapter.build_close_payload(
        trade_id="fut-dup",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="NQ",
        entry_price=18000.0,
        exit_price=18030.0,
        quantity=1.0,
        realized_pnl=30.0,
        strategy_id="futures_mean_reversion",
        market_regime="risk_on",
        broker="SIM",
    )

    adapter.persist_closed_trade_outcome(close_payload)

    with pytest.raises(CanonicalTradeLifecycleError):
        adapter.persist_closed_trade_outcome(close_payload)

    invalid_close_payload = dict(close_payload)
    invalid_close_payload["realized_pnl"] = None

    with pytest.raises(CanonicalTradeLifecycleError):
        adapter.persist_closed_trade_outcome(invalid_close_payload)
