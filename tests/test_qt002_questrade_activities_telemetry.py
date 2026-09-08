
import pytest

from backend.app.brokers.operational_state import BrokerOperationalState
from backend.brokers.questrade.errors import ProviderUnavailableError
from backend.brokers.questrade.live_readonly_provider import (
    QuestradeLiveReadOnlyDataProvider,
)
from backend.brokers.questrade.readonly_client import QuestradeHttpResult


class StubClient:
    def __init__(self):
        self.calls = []

    def request(self, path, *, method="GET", params=None, **kwargs):
        self.calls.append(
            {
                "path": path,
                "method": method,
                "params": dict(params or {}),
            }
        )
        return QuestradeHttpResult(
            success=True,
            state=BrokerOperationalState.READ_ONLY_READY,
            payload={"activities": []},
        )


def _window():
    return {
        "startTime": "2026-09-08T00:00:00-04:00",
        "endTime": "2026-09-08T23:59:59-04:00",
    }


def test_qt002_activities_routes_to_allowlisted_account_endpoint():
    client = StubClient()
    provider = QuestradeLiveReadOnlyDataProvider(
        client,
        account_reference="28776573",
    )

    result = provider.fetch(
        "ACTIVITIES",
        authorization=memoryview(b"lease"),
        parameters=_window(),
    )

    assert result["activities"] == []
    assert len(client.calls) == 1

    call = client.calls[0]
    assert call["path"] == "/accounts/28776573/activities"
    assert call["method"] == "GET"
    assert call["params"] == _window()


def test_qt002_activities_requires_start_and_end_time():
    client = StubClient()
    provider = QuestradeLiveReadOnlyDataProvider(
        client,
        account_reference="28776573",
    )

    with pytest.raises(ProviderUnavailableError) as exc:
        provider.fetch(
            "ACTIVITIES",
            authorization=memoryview(b"lease"),
            parameters={},
        )

    assert "QUESTRADE_ACTIVITIES_DATE_RANGE_REQUIRED" in str(exc.value)
    assert client.calls == []


def test_qt002_activities_missing_end_time_fails_closed():
    client = StubClient()
    provider = QuestradeLiveReadOnlyDataProvider(
        client,
        account_reference="28776573",
    )

    with pytest.raises(ProviderUnavailableError):
        provider.fetch(
            "ACTIVITIES",
            authorization=memoryview(b"lease"),
            parameters={
                "startTime": "2026-09-08T00:00:00-04:00",
            },
        )

    assert client.calls == []


def test_qt002_provider_never_requests_write_method():
    client = StubClient()
    provider = QuestradeLiveReadOnlyDataProvider(
        client,
        account_reference="28776573",
    )

    provider.fetch(
        "ACTIVITIES",
        authorization=memoryview(b"lease"),
        parameters=_window(),
    )

    assert client.calls
    assert all(call["method"] == "GET" for call in client.calls)


def test_qt002_orders_remain_unsupported():
    client = StubClient()
    provider = QuestradeLiveReadOnlyDataProvider(
        client,
        account_reference="28776573",
    )

    with pytest.raises(ProviderUnavailableError):
        provider.fetch(
            "ORDERS",
            authorization=memoryview(b"lease"),
            parameters={},
        )

    assert client.calls == []
