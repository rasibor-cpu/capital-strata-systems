from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.brokers.readonly_adapters import QuestradeReadOnlyBrokerAdapter
from backend.brokers.readonly_reconciliation import reconcile_portfolios
from backend.brokers.replay_provider import ReplayBrokerProvider, ReplayScenario
from dashboard.runtime.mission_control_state import build_mission_control_state


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def test_mission_control_distinguishes_replay_stale_and_unavailable():
    replay = ReplayBrokerProvider(now=NOW).snapshot()
    replay_state = build_mission_control_state({"broker_name": "REPLAY", "status": "AVAILABLE", "timestamp": NOW.isoformat(), "balances": {"cash": "5000", "equity": "10000"}, "positions": []}, portfolio_snapshot=replay)
    stale = ReplayBrokerProvider(ReplayScenario.STALE_DATA, now=NOW).snapshot()
    stale_state = build_mission_control_state({"broker_name": "REPLAY", "status": "AVAILABLE", "timestamp": NOW.isoformat(), "balances": {}, "positions": []}, portfolio_snapshot=stale)
    unavailable_state = build_mission_control_state({"broker_name": "REPLAY", "status": "UNAVAILABLE"})
    assert replay_state.portfolio_snapshot_source == "REPLAY"
    assert stale_state.portfolio_snapshot_source == "STALE"
    assert unavailable_state.data_freshness == "UNAVAILABLE"
    for state in (replay_state, stale_state, unavailable_state):
        assert state.execution_allowed is False
        assert state.live_trading_blocked is True
        assert state.broker_execution_armed is False
        assert state.advisory_only is True


def test_recovery_returns_fresh_read_only_snapshot():
    stale = ReplayBrokerProvider(ReplayScenario.STALE_DATA, now=NOW).snapshot()
    fresh = ReplayBrokerProvider(ReplayScenario.NORMAL_PORTFOLIO, now=NOW).snapshot()
    assert stale.snapshot_source.value == "STALE"
    assert fresh.snapshot_source.value == "REPLAY"
    assert fresh.broker_data_freshness == "FRESH"


def test_provider_boundary_is_interchangeable_after_normalization():
    replay = ReplayBrokerProvider(now=NOW).snapshot()
    payload = {
        "accounts": [{"number": "LIVE-1", "currency": "CAD"}],
        "balances": {"currency": "CAD", "cash": "5000", "buying_power": "7000", "equity": "10000"},
        "positions": [{"symbol": p.symbol, "quantity": str(p.quantity), "averageEntryPrice": str(p.average_cost), "currentPrice": str(p.market_price), "currentMarketValue": str(p.market_value), "openPnl": str(p.unrealized_pnl), "closedPnl": str(p.realized_pnl), "currency": p.currency} for p in replay.positions],
    }
    fake_client = SimpleNamespace(
        get_accounts=lambda: payload,
        get_balances=lambda account_id: payload["balances"],
        get_positions=lambda account_id: {"positions": payload["positions"]},
        get_orders=lambda account_id, **query: {"orders": []},
        get_executions=lambda account_id, **query: {"executions": []},
        get_activities=lambda account_id, start, end: [],
    )
    live = QuestradeReadOnlyBrokerAdapter(fake_client)
    account = live.get_accounts()[0]
    balance = live.get_balances(account.account_id)
    positions = live.get_positions(account.account_id)
    assert balance.cash == replay.cash
    assert tuple(position.symbol for position in positions) == tuple(position.symbol for position in replay.positions)
    assert sum((position.market_value for position in positions if position.market_value), Decimal("0")) == replay.market_value


def test_reconciliation_stale_is_explicit_and_no_authority_transfer():
    broker = ReplayBrokerProvider(ReplayScenario.STALE_DATA, now=NOW).snapshot()
    result = reconcile_portfolios(broker, None)
    assert result.status == "ISSUES"
    assert any(item.category.value == "STALE_DATA" for item in result.findings)
    assert broker.snapshot_source.value == "STALE"
