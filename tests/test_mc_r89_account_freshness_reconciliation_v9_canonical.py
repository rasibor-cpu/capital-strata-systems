from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]

COORDINATOR_PATH = (
    ROOT
    / "backend"
    / "brokers"
    / "questrade"
    / "mission_control_activation.py"
)

PUBLISHER_PATH = (
    ROOT
    / "backend"
    / "runtime"
    / "runtime_artifact_publisher.py"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coordinator_mod = _load_module(
    "css_r89v9_activation",
    COORDINATOR_PATH,
)
publisher_mod = _load_module(
    "css_r89v9_publisher",
    PUBLISHER_PATH,
)

QuestradeMissionControlActivationCoordinator = (
    coordinator_mod.QuestradeMissionControlActivationCoordinator
)
RuntimeArtifactPublisher = publisher_mod.RuntimeArtifactPublisher


class FakeCache:
    def __init__(self):
        self.snapshot = None
        self.publish_count = 0

    def read(self):
        return self.snapshot

    def publish(self, snapshot):
        self.snapshot = dict(snapshot)
        self.publish_count += 1
        return dict(self.snapshot)


class FakeProvider:
    def __init__(self):
        self.calls = []

    def bind_account_reference(self, account_reference):
        self.calls.append(("BIND", account_reference))

    def fetch(self, endpoint, *, authorization, parameters):
        self.calls.append((endpoint, dict(parameters)))

        if endpoint == "ACCOUNTS":
            return {
                "accounts": [
                    {
                        "number": "TEST-ACCOUNT",
                        "isPrimary": True,
                        "status": "ACTIVE",
                    }
                ]
            }

        if endpoint == "BALANCES":
            return {
                "acquisition_timestamp": "2026-09-07T04:30:00Z",
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

        if endpoint == "POSITIONS":
            return {
                "acquisition_timestamp": "2026-09-07T04:30:00Z",
                "positions": [],
            }

        raise AssertionError(f"unexpected endpoint: {endpoint}")


class FakeActivation:
    def __init__(self, provider):
        self.provider = provider

    def as_dict(self):
        return {
            "activated": True,
            "reason": "ok",
        }


def test_v9_callback_fires_after_activation_and_refresh():
    cache = FakeCache()
    provider = FakeProvider()
    callback_calls = []

    coordinator = QuestradeMissionControlActivationCoordinator(
        cache,
        composer=lambda **kwargs: FakeActivation(provider),
        on_fresh_snapshot=lambda: callback_calls.append("fresh"),
    )

    activated = coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )

    assert activated["status"] == "READY"
    assert callback_calls == ["fresh"]
    assert cache.publish_count == 1

    refreshed = coordinator.refresh()

    assert refreshed["status"] == "READY"
    assert refreshed["reason"] == "refreshed"
    assert callback_calls == ["fresh", "fresh"]
    assert cache.publish_count == 2

    assert activated["execution_allowed"] is False
    assert activated["live_trading_blocked"] is True
    assert activated["broker_execution_armed"] is False
    assert activated["advisory_only"] is True

    assert refreshed["execution_allowed"] is False
    assert refreshed["live_trading_blocked"] is True
    assert refreshed["broker_execution_armed"] is False
    assert refreshed["advisory_only"] is True


def test_v9_callback_failure_does_not_break_read_only_activation():
    cache = FakeCache()
    provider = FakeProvider()

    def broken_callback():
        raise RuntimeError("expected test callback failure")

    coordinator = QuestradeMissionControlActivationCoordinator(
        cache,
        composer=lambda **kwargs: FakeActivation(provider),
        on_fresh_snapshot=broken_callback,
    )

    activated = coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )

    assert activated["status"] == "READY"
    assert cache.publish_count == 1
    assert cache.read() is not None

    refreshed = coordinator.refresh()

    assert refreshed["status"] == "READY"
    assert cache.publish_count == 2

    assert refreshed["execution_allowed"] is False
    assert refreshed["live_trading_blocked"] is True
    assert refreshed["broker_execution_armed"] is False
    assert refreshed["advisory_only"] is True


def test_v9_no_callback_preserves_backward_compatibility():
    cache = FakeCache()
    provider = FakeProvider()

    coordinator = QuestradeMissionControlActivationCoordinator(
        cache,
        composer=lambda **kwargs: FakeActivation(provider),
    )

    result = coordinator.activate(
        refresh_token_store_path="C:/fake/token.dpapi"
    )

    assert result["status"] == "READY"
    assert cache.publish_count == 1


def test_v9_account_only_publisher_writes_only_account_artifact(tmp_path):
    publisher = RuntimeArtifactPublisher(
        artifacts_dir=tmp_path,
    )

    unrelated = {
        "css_session_state_pcnrass.json": {"existing": True},
        "runtime_portfolio_state.json": {"existing": True},
        "runtime_advisory_snapshot.json": {"existing": True},
        "portfolio_snapshot.json": {"existing": True},
        "portfolio_decision.json": {"existing": True},
        "validation_summary.json": {"existing": True},
    }

    before = {}

    for filename, payload in unrelated.items():
        path = tmp_path / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        old_time = time.time() - 60.0
        path.touch()
        import os
        os.utime(path, (old_time, old_time))
        before[filename] = path.stat().st_mtime_ns

    account_state = {
        "status": "AVAILABLE",
        "source": "QUESTRADE_LIVE_READ_ONLY",
        "broker": "QUESTRADE",
        "account_mode": "LIVE_READ_ONLY",
        "timestamp": "2026-09-07T04:30:00Z",
        "cash": -99.130056,
        "equity": 1569.428972,
        "buying_power": 3556.642978,
        "available_balance": None,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority": False,
        "broker_execution_enabled": False,
        "live_trading_enabled": False,
        "can_live_execute": False,
        "live_order_permission": False,
        "order_submission_status": "DISABLED",
        "execution_scope": "LIVE_READ_ONLY",
    }

    result = publisher.publish_account_state(
        account_state,
        runtime_cycle=1,
        session_id="TEST-SESSION",
        runtime_version="TEST",
        timestamp="2026-09-07T04:30:01Z",
    )

    assert result["status"] == "OK"
    assert result["execution_allowed"] is False
    assert result["advisory_only"] is True

    account_path = tmp_path / "css_account_state_pcnrass.json"
    assert account_path.exists()

    payload = json.loads(account_path.read_text(encoding="utf-8"))

    assert payload["source"] == "QUESTRADE_LIVE_READ_ONLY"
    assert payload["broker"] == "QUESTRADE"
    assert payload["execution_allowed"] is False
    assert payload["advisory_only"] is True
    assert payload["live_trading_blocked"] is True
    assert payload["broker_execution_armed"] is False

    assert set(result["published_artifacts"]) == {
        "css_account_state_pcnrass.json"
    }

    for filename, old_mtime in before.items():
        path = tmp_path / filename
        assert path.stat().st_mtime_ns == old_mtime


def test_v9_account_only_publisher_does_not_create_unrelated_artifacts(
    tmp_path,
):
    publisher = RuntimeArtifactPublisher(
        artifacts_dir=tmp_path,
    )

    result = publisher.publish_account_state(
        {
            "status": "AVAILABLE",
            "source": "QUESTRADE_LIVE_READ_ONLY",
            "broker": "QUESTRADE",
            "timestamp": "2026-09-07T04:30:00Z",
            "cash": 1.0,
            "equity": 2.0,
            "buying_power": 3.0,
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
        runtime_cycle=1,
    )

    assert result["status"] == "OK"

    names = sorted(path.name for path in tmp_path.iterdir())

    assert names == ["css_account_state_pcnrass.json"]


def test_v9_account_only_publisher_rejects_non_mapping(tmp_path):
    publisher = RuntimeArtifactPublisher(
        artifacts_dir=tmp_path,
    )

    try:
        publisher.publish_account_state(None)
    except publisher_mod.RuntimeArtifactPublisherError:
        pass
    else:
        raise AssertionError(
            "non-mapping account state should fail closed"
        )


def test_v9_coordinator_source_contains_no_execution_enablement():
    source = COORDINATOR_PATH.read_text(encoding="utf-8")

    forbidden = [
        '"execution_allowed": True',
        '"live_trading_blocked": False',
        '"broker_execution_armed": True',
        '"advisory_only": False',
    ]

    for token in forbidden:
        assert token not in source


def test_v9_publisher_source_account_only_method_is_narrow():
    source = PUBLISHER_PATH.read_text(encoding="utf-8")

    start = source.index("    def publish_account_state(")
    end = source.index(
        "    def _build_portfolio_state",
        start,
    )

    method = source[start:end]

    assert '"css_account_state_pcnrass.json"' in method

    forbidden = [
        "runtime_portfolio_state.json",
        "runtime_advisory_snapshot.json",
        "portfolio_snapshot.json",
        "portfolio_decision.json",
        "validation_summary.json",
        "css_session_state_pcnrass.json",
    ]

    for filename in forbidden:
        assert filename not in method
