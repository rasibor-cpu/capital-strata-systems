from __future__ import annotations

import pytest

from backend.analytics.trade_outcome_repository import TradeOutcomeRepository, build_trade_outcome_analytics_adapter
from backend.app.options.options_lifecycle_adapter import OptionsLifecycleAdapter
from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycleError


@pytest.fixture
def repo(tmp_path):
    repository = TradeOutcomeRepository(tmp_path / "options_outcomes.json")
    repository.create_storage()
    return repository


@pytest.fixture
def adapter(repo):
    return OptionsLifecycleAdapter(repository=repo)


def test_options_open_and_close_normalization(adapter):
    open_payload = adapter.build_open_payload(
        trade_id="opt-001",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="SPY-C-500",
        entry_price=500.0,
        exit_price=505.0,
        quantity=1.0,
        strategy_id="options_mean_reversion",
        market_regime="risk_on",
        broker="SIM",
    )

    normalized_open = adapter.normalize_open_result(open_payload)

    assert normalized_open["asset_class"] == "OPTIONS"
    assert normalized_open["symbol"] == "SPY-C-500"
    assert normalized_open["broker"] == "SIM"

    close_payload = adapter.build_close_payload(
        trade_id="opt-001",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="SPY-C-500",
        entry_price=500.0,
        exit_price=505.0,
        quantity=1.0,
        realized_pnl=5.0,
        strategy_id="options_mean_reversion",
        market_regime="risk_on",
        broker="SIM",
    )

    normalized_close = adapter.normalize_close_result(close_payload)
    assert normalized_close["asset_class"] == "OPTIONS"
    assert normalized_close["realized_pnl"] == 5.0


def test_options_paper_mode_and_warehouse_persistence(adapter):
    paper_result = adapter.execute_paper_order(
        symbol="SPY-C-500",
        side="BUY",
        contracts=1,
        mode="paper",
    )

    assert paper_result["approved"] is True
    assert paper_result["dry_run"] is True

    close_payload = adapter.build_close_payload(
        trade_id="opt-warehouse",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="SPY-C-500",
        entry_price=500.0,
        exit_price=505.0,
        quantity=1.0,
        realized_pnl=5.0,
        strategy_id="options_mean_reversion",
        market_regime="risk_on",
        broker="SIM",
    )

    persisted = adapter.persist_closed_trade_outcome(close_payload)
    assert persisted["trade_id"] == "opt-warehouse"

    analytics = build_trade_outcome_analytics_adapter(adapter.repository)
    assert analytics["top_asset_classes"][0]["asset_class"] == "OPTIONS"


def test_options_duplicate_prevention_and_fail_closed(adapter):
    close_payload = adapter.build_close_payload(
        trade_id="opt-dup",
        timestamp_open="2026-06-24T10:00:00+00:00",
        timestamp_close="2026-06-24T10:05:00+00:00",
        symbol="QQQ-C-400",
        entry_price=400.0,
        exit_price=405.0,
        quantity=1.0,
        realized_pnl=5.0,
        strategy_id="options_mean_reversion",
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
