from __future__ import annotations

from datetime import datetime, timezone

from backend.brokers.questrade.mission_control_activation import (
    QuestradeMissionControlActivationCoordinator,
)
from backend.brokers.questrade.mission_control_cache import QuestradeMissionControlCache


def _fresh_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Provider:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_next_balances = False
        self.bound_account_reference: str | None = None

    def bind_account_reference(self, account_reference: str) -> None:
        self.bound_account_reference = account_reference

    def fetch(self, resource, *, authorization, parameters):
        self.calls.append(resource)

        if resource == "ACCOUNTS":
            return {
                "accounts": [
                    {
                        "number": "28776573",
                        "isPrimary": True,
                        "status": "Active",
                    }
                ]
            }

        if resource == "BALANCES":
            if self.fail_next_balances:
                self.fail_next_balances = False
                raise RuntimeError("TRANSIENT_BALANCE_FAILURE")
            return {
                "acquisition_timestamp": _fresh_timestamp(),
                "combinedBalances": [
                    {
                        "currency": "CAD",
                        "cash": -99.130056,
                        "marketValue": 1668.559028,
                        "totalEquity": 1569.428972,
                        "buyingPower": 3556.642978,
                    }
                ],
            }

        if resource == "POSITIONS":
            return {
                "acquisition_timestamp": _fresh_timestamp(),
                "positions": [],
            }

        raise AssertionError(f"unexpected resource: {resource}")


class _Activation:
    def __init__(self, provider: _Provider) -> None:
        self.provider = provider

    def as_dict(self):
        return {
            "activated": True,
            "reason": "ok",
        }


def test_r88_transient_refresh_failure_keeps_existing_provider_retryable():
    cache = QuestradeMissionControlCache()
    provider = _Provider()
    composer_calls = 0

    def composer(**kwargs):
        nonlocal composer_calls
        composer_calls += 1
        assert kwargs["activation_authorized"] is True
        return _Activation(provider)

    coordinator = QuestradeMissionControlActivationCoordinator(
        cache,
        composer=composer,
    )

    activated = coordinator.activate(
        refresh_token_store_path="unused-test-path",
    )
    assert activated["status"] == "READY"
    assert activated["provider_available"] is True
    assert activated["execution_allowed"] is False
    assert activated["live_trading_blocked"] is True
    assert activated["broker_execution_armed"] is False
    assert activated["advisory_only"] is True
    assert composer_calls == 1
    assert provider.calls == ["ACCOUNTS", "BALANCES", "POSITIONS"]

    provider.fail_next_balances = True

    failed = coordinator.refresh()
    assert failed["status"] == "UNAVAILABLE"
    assert failed["provider_available"] is True
    assert failed["execution_allowed"] is False
    assert failed["live_trading_blocked"] is True
    assert failed["broker_execution_armed"] is False
    assert failed["advisory_only"] is True

    recovered = coordinator.refresh()
    assert recovered["status"] == "READY"
    assert recovered["reason"] == "refreshed"
    assert recovered["provider_available"] is True
    assert recovered["execution_allowed"] is False
    assert recovered["live_trading_blocked"] is True
    assert recovered["broker_execution_armed"] is False
    assert recovered["advisory_only"] is True

    assert composer_calls == 1
    assert provider.calls.count("ACCOUNTS") == 1
    assert provider.calls == [
        "ACCOUNTS",
        "BALANCES",
        "POSITIONS",
        "BALANCES",
        "BALANCES",
        "POSITIONS",
    ]
