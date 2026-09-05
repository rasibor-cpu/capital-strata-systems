from datetime import datetime, timezone

from backend.brokers.questrade.mission_control_activation import QuestradeMissionControlActivationCoordinator
from backend.brokers.questrade.mission_control_cache import QuestradeMissionControlCache


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.bound = None

    def bind_account_reference(self, value):
        self.bound = value

    def fetch(self, dataset, *, authorization, parameters):
        self.calls.append((dataset, dict(parameters)))
        ts = datetime.now(timezone.utc).isoformat()
        if dataset == "ACCOUNTS":
            return {"accounts": [{"number": "SECRET-1234", "status": "Active", "isPrimary": True}]}
        if dataset == "BALANCES":
            return {"acquisition_timestamp": ts, "combinedBalances": [{"currency": "CAD", "cash": 10.0, "totalEquity": 20.0}]}
        if dataset == "POSITIONS":
            return {"acquisition_timestamp": ts, "positions": [{"symbol": "TD", "openQuantity": 1, "currentMarketValue": 10.0}]}
        raise AssertionError(dataset)


class FakeActivation:
    def __init__(self, provider, *, activated=True, reason="ok"):
        self.provider = provider
        self._payload = {"activated": activated, "status": "READY" if activated else "UNAVAILABLE", "reason": reason}

    def as_dict(self):
        return dict(self._payload)


def test_r85_activation_fetches_once_and_publishes_sanitized_snapshot():
    cache = QuestradeMissionControlCache()
    provider = FakeProvider()
    calls = {"compose": 0}
    def composer(**kwargs):
        calls["compose"] += 1
        assert kwargs["activation_authorized"] is True
        return FakeActivation(provider)
    coordinator = QuestradeMissionControlActivationCoordinator(cache, composer=composer)
    result = coordinator.activate(refresh_token_store_path="C:/fake/token.dpapi")
    assert result["status"] == "READY"
    assert calls["compose"] == 1
    assert [row[0] for row in provider.calls] == ["ACCOUNTS", "BALANCES", "POSITIONS"]
    assert provider.bound == "SECRET-1234"
    snapshot = cache.read()
    assert snapshot is not None
    assert snapshot["selected_broker"] == "QUESTRADE"
    assert "SECRET-1234" not in repr(snapshot)
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True


def test_r85_second_activation_does_not_repeat_oauth_or_network():
    cache = QuestradeMissionControlCache()
    provider = FakeProvider()
    calls = {"compose": 0}
    def composer(**kwargs):
        calls["compose"] += 1
        return FakeActivation(provider)
    coordinator = QuestradeMissionControlActivationCoordinator(cache, composer=composer)
    assert coordinator.activate(refresh_token_store_path="C:/fake/token.dpapi")["status"] == "READY"
    before = list(provider.calls)
    again = coordinator.activate(refresh_token_store_path="C:/fake/token.dpapi")
    assert again["status"] == "READY"
    assert calls["compose"] == 1
    assert provider.calls == before


def test_r85_failed_activation_is_not_retried_in_same_process():
    cache = QuestradeMissionControlCache()
    calls = {"compose": 0}
    def composer(**kwargs):
        calls["compose"] += 1
        return FakeActivation(None, activated=False, reason="TEST_FAILURE")
    coordinator = QuestradeMissionControlActivationCoordinator(cache, composer=composer)
    first = coordinator.activate(refresh_token_store_path="C:/fake/token.dpapi")
    second = coordinator.activate(refresh_token_store_path="C:/fake/token.dpapi")
    assert first["status"] == "UNAVAILABLE"
    assert second["status"] == "UNAVAILABLE"
    assert calls["compose"] == 1


def test_r85_ambiguous_accounts_fail_closed_without_balance_or_position_fetch():
    cache = QuestradeMissionControlCache()
    class AmbiguousProvider(FakeProvider):
        def fetch(self, dataset, *, authorization, parameters):
            self.calls.append((dataset, dict(parameters)))
            if dataset == "ACCOUNTS":
                return {"accounts": [{"number": "A"}, {"number": "B"}]}
            raise AssertionError("unexpected downstream fetch")
    provider = AmbiguousProvider()
    coordinator = QuestradeMissionControlActivationCoordinator(cache, composer=lambda **kwargs: FakeActivation(provider))
    result = coordinator.activate(refresh_token_store_path="C:/fake/token.dpapi")
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "QUESTRADE_ACCOUNT_SELECTION_REQUIRED"
    assert [row[0] for row in provider.calls] == ["ACCOUNTS"]
    assert cache.read() is None

def test_r85_refresh_reuses_provider_without_second_oauth():
    cache = QuestradeMissionControlCache()
    provider = FakeProvider()
    calls = {"compose": 0}
    def composer(**kwargs):
        calls["compose"] += 1
        return FakeActivation(provider)
    coordinator = QuestradeMissionControlActivationCoordinator(cache, composer=composer)
    assert coordinator.activate(refresh_token_store_path="C:/fake/token.dpapi")["status"] == "READY"
    initial_calls = len(provider.calls)
    refreshed = coordinator.refresh()
    assert refreshed["status"] == "READY"
    assert refreshed["reason"] == "refreshed"
    assert calls["compose"] == 1
    assert len(provider.calls) == initial_calls + 2
    assert [row[0] for row in provider.calls[-2:]] == ["BALANCES", "POSITIONS"]


def test_r85_refresh_before_activation_fails_closed_without_oauth():
    cache = QuestradeMissionControlCache()
    calls = {"compose": 0}
    def composer(**kwargs):
        calls["compose"] += 1
        raise AssertionError("OAuth composer must not run during refresh")
    coordinator = QuestradeMissionControlActivationCoordinator(cache, composer=composer)
    result = coordinator.refresh()
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "QUESTRADE_NOT_ACTIVATED"
    assert calls["compose"] == 0
