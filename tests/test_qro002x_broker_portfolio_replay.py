from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.brokers.readonly_domain import BrokerPosition, PortfolioSnapshot, SnapshotSource, BrokerRateLimitedError, BrokerProviderError
from backend.brokers.readonly_reconciliation import ReconciliationCategory, reconcile_portfolios
from backend.brokers.replay_provider import ReplayBrokerProvider, ReplayScenario


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def test_replay_normal_snapshot_is_deterministic_decimal_and_read_only():
    first = ReplayBrokerProvider(now=NOW).snapshot()
    second = ReplayBrokerProvider(now=NOW).snapshot()
    assert first.as_dict() == second.as_dict()
    assert first.snapshot_source is SnapshotSource.REPLAY
    assert first.cash == Decimal("5000")
    assert first.total_equity == Decimal("10000")
    assert first.positions[0].symbol == "SHOP"
    assert not {"place_order", "submit_order", "cancel_order", "transfer", "withdraw"}.intersection(dir(ReplayBrokerProvider()))


def test_replay_account_selection_fails_closed():
    with pytest.raises(Exception, match="PROVIDER_RESPONSE_ERROR"):
        ReplayBrokerProvider(ReplayScenario.EMPTY_PORTFOLIO).select_account()
    with pytest.raises(RuntimeError, match="CONFIGURATION_REQUIRED"):
        ReplayBrokerProvider(ReplayScenario.MULTI_ACCOUNT).select_account()
    assert ReplayBrokerProvider(ReplayScenario.MULTI_ACCOUNT).select_account("REPLAY-CAD-001").currency == "CAD"


@pytest.mark.parametrize("scenario, error", [(ReplayScenario.PROVIDER_UNAVAILABLE, BrokerProviderError), (ReplayScenario.PROVIDER_RATE_LIMITED, BrokerRateLimitedError)])
def test_replay_provider_failure_modes(scenario, error):
    with pytest.raises(error):
        ReplayBrokerProvider(scenario).get_accounts()


def test_stale_and_partial_data_are_explicit():
    stale = ReplayBrokerProvider(ReplayScenario.STALE_DATA, now=NOW).snapshot()
    partial = ReplayBrokerProvider(ReplayScenario.PARTIAL_RESPONSE, now=NOW).snapshot()
    assert stale.snapshot_source is SnapshotSource.STALE
    assert stale.broker_data_freshness == "STALE"
    assert partial.market_value is None
    assert partial.reason == "PARTIAL_RESPONSE"


def test_reconciliation_reports_mismatch_without_overwriting_broker_truth():
    broker = ReplayBrokerProvider(now=NOW).snapshot()
    css_position = BrokerPosition("CSS", "SHOP", Decimal("1"), Decimal("80"), Decimal("90"), Decimal("90"), Decimal("10"), None, "CAD", NOW)
    css = PortfolioSnapshot("****CSS", NOW, "CAD", Decimal("5000"), Decimal("7000"), Decimal("10000"), Decimal("90"), (css_position,))
    result = reconcile_portfolios(broker, css)
    assert result.status == "ISSUES"
    assert any(item.category is ReconciliationCategory.QUANTITY_MISMATCH for item in result.findings)
    assert broker.positions[0].quantity == Decimal("10")


def test_duplicate_activities_are_classified():
    provider = ReplayBrokerProvider(ReplayScenario.DUPLICATE_ACTIVITY, now=NOW)
    result = reconcile_portfolios(provider.snapshot(), None, activities=provider.get_activities("REPLAY-CAD-001"))
    assert any(item.category is ReconciliationCategory.DUPLICATE_ACTIVITY for item in result.findings)


def test_css_attribution_is_not_inferred_from_broker_pnl():
    snapshot = ReplayBrokerProvider(now=NOW).snapshot()
    assert "css_attributed" not in snapshot.as_dict()
    assert snapshot.total_unrealized_pnl == Decimal("59")
