from datetime import datetime, timezone

from backend.brokers.questrade.mission_control_activation import (
    QuestradeMissionControlActivationCoordinator,
)
from backend.brokers.questrade.mission_control_cache import (
    QuestradeMissionControlCache,
)


def _ts():
    return datetime.now(timezone.utc).isoformat()


class Provider:
    def __init__(self, *, activities=None, activities_failure=None):
        self.calls = []
        self.activity_parameters = None
        self.activities = [] if activities is None else activities
        self.activities_failure = activities_failure
        self.bound = None

    def bind_account_reference(self, value):
        self.bound = value

    def fetch(self, dataset, *, authorization, parameters):
        self.calls.append(dataset)

        assert authorization is not None
        assert len(authorization) > 0

        if dataset == "ACCOUNTS":
            return {
                "accounts": [
                    {
                        "number": "SECRET-6573",
                        "status": "Active",
                        "isPrimary": True,
                    }
                ]
            }

        if dataset == "BALANCES":
            return {
                "acquisition_timestamp": _ts(),
                "combinedBalances": [],
            }

        if dataset == "POSITIONS":
            return {
                "acquisition_timestamp": _ts(),
                "positions": [],
            }

        if dataset == "ACTIVITIES":
            self.activity_parameters = dict(parameters)
            if self.activities_failure is not None:
                raise self.activities_failure
            return {
                "acquisition_timestamp": _ts(),
                "activities": list(self.activities),
            }

        raise AssertionError(dataset)


class Activation:
    def __init__(self, provider):
        self.provider = provider

    def as_dict(self):
        return {
            "activated": True,
            "status": "READY",
            "reason": "ok",
        }


def _coordinator(provider):
    cache = QuestradeMissionControlCache()
    coordinator = QuestradeMissionControlActivationCoordinator(
        cache,
        composer=lambda **kwargs: Activation(provider),
    )
    return cache, coordinator


def test_qt003_activation_publishes_recent_activity_history_separately():
    provider = Provider(
        activities=[
            {
                "symbol": "TD",
                "action": "Sell",
                "quantity": 5,
            }
        ]
    )
    cache, coordinator = _coordinator(provider)

    result = coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )

    assert result["status"] == "READY"
    assert provider.calls == [
        "ACCOUNTS",
        "BALANCES",
        "POSITIONS",
        "ACTIVITIES",
    ]

    snapshot = cache.read()
    assert snapshot is not None
    assert snapshot["activities"]["status"] == "AVAILABLE"
    assert snapshot["activities"]["activity_count"] == 1
    assert snapshot["activities"]["activities"][0]["symbol"] == "TD"

    # Activity history must never become current-position evidence.
    assert snapshot["positions"]["positions"] == []


def test_qt003_activity_request_has_bounded_explicit_date_window():
    provider = Provider()
    _, coordinator = _coordinator(provider)

    result = coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )

    assert result["status"] == "READY"

    params = provider.activity_parameters
    assert params is not None
    assert params["account_reference"] == "SECRET-6573"
    assert params["startTime"]
    assert params["endTime"]
    assert params["startTime"] < params["endTime"]


def test_qt003_empty_activity_result_is_valid_available_evidence():
    provider = Provider(activities=[])
    cache, coordinator = _coordinator(provider)

    assert coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )["status"] == "READY"

    snapshot = cache.read()
    assert snapshot is not None
    assert snapshot["activities"]["status"] == "AVAILABLE"
    assert snapshot["activities"]["activity_count"] == 0
    assert snapshot["activities"]["activities"] == []


def test_qt003_activity_failure_does_not_invalidate_balances_or_positions():
    provider = Provider(
        activities_failure=RuntimeError("ACTIVITY_TEMPORARILY_UNAVAILABLE")
    )
    cache, coordinator = _coordinator(provider)

    result = coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )

    assert result["status"] == "READY"

    snapshot = cache.read()
    assert snapshot is not None

    assert snapshot["balances"]["combinedBalances"] == []
    assert snapshot["positions"]["positions"] == []

    activities = snapshot["activities"]
    assert activities["status"] == "UNAVAILABLE"
    assert activities["activity_count"] == 0
    assert activities["activities"] == []

    assert activities["execution_allowed"] is False
    assert activities["live_trading_blocked"] is True
    assert activities["broker_execution_armed"] is False
    assert activities["advisory_only"] is True


def test_qt003_refresh_reuses_provider_and_refreshes_activity_history():
    provider = Provider()
    cache, coordinator = _coordinator(provider)

    assert coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )["status"] == "READY"

    initial = list(provider.calls)

    result = coordinator.refresh()

    assert result["status"] == "READY"
    assert result["reason"] == "refreshed"
    assert provider.calls[len(initial):] == [
        "BALANCES",
        "POSITIONS",
        "ACTIVITIES",
    ]

    assert cache.read() is not None


def test_qt003_snapshot_retains_fail_closed_safety_flags():
    provider = Provider()
    cache, coordinator = _coordinator(provider)

    assert coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )["status"] == "READY"

    snapshot = cache.read()
    assert snapshot is not None
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True
    assert snapshot["broker_execution_armed"] is False
    assert snapshot["advisory_only"] is True
