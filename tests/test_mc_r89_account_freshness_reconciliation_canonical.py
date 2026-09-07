import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLISHER_CANDIDATE = (
    REPO_ROOT
    / "backend"
    / "runtime"
    / "runtime_artifact_publisher_R89.py"
)

LAUNCHER_CANDIDATE = (
    REPO_ROOT
    / "launcher"
    / "css_mobile_launcher.py"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def publisher_module():
    return _load_module(
        "runtime_artifact_publisher_R89_candidate",
        PUBLISHER_CANDIDATE,
    )


@pytest.fixture(scope="module")
def launcher_module():
    return _load_module(
        "css_mobile_launcher_R89_candidate",
        LAUNCHER_CANDIDATE,
    )


def _runtime_state() -> dict:
    return {
        "status": "OK",
        "portfolio_state": "NO_PORTFOLIO",
        "account": {
            "equity": 10000,
            "cash": 9000,
            "buying_power": 9000,
            "realized_pnl": 0,
            "open_pnl": 0,
            "total_pnl": 0,
        },
        "positions": [],
        "trades": [],
        "asset_allocations": {},
        "advisory_only": True,
        "execution_allowed": False,
    }


def _fresh_questrade_snapshot() -> dict:
    ts = datetime.now(timezone.utc).isoformat()

    return {
        "status": "AVAILABLE",
        "acquisition_timestamp": ts,
        "balances": {
            "acquisition_timestamp": ts,
            "combinedBalances": [
                {
                    "currency": "CAD",
                    "cash": -99.130056,
                    "marketValue": 1668.559028,
                    "totalEquity": 1569.428972,
                    "buyingPower": 3556.642978,
                }
            ],
        },
        "positions": {
            "acquisition_timestamp": ts,
            "positions": [],
        },
    }


def test_r89_default_publisher_still_writes_account_artifact(
    tmp_path: Path,
    publisher_module,
) -> None:
    result = publisher_module.RuntimeArtifactPublisher(
        artifacts_dir=tmp_path
    ).publish(
        runtime_cycle=7,
        runtime_portfolio_state=_runtime_state(),
        timestamp="2026-09-07T03:00:00+00:00",
    )

    account_path = tmp_path / "css_account_state_pcnrass.json"

    assert result["status"] in {"OK", "AMBER"}
    assert account_path.is_file()

    payload = json.loads(
        account_path.read_text(encoding="utf-8")
    )

    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False


def test_r89_publish_account_false_does_not_create_account_artifact(
    tmp_path: Path,
    publisher_module,
) -> None:
    result = publisher_module.RuntimeArtifactPublisher(
        artifacts_dir=tmp_path
    ).publish(
        runtime_cycle=7,
        runtime_portfolio_state=_runtime_state(),
        publish_account_state=False,
        timestamp="2026-09-07T03:00:00+00:00",
    )

    account_path = tmp_path / "css_account_state_pcnrass.json"
    session_path = tmp_path / "css_session_state_pcnrass.json"
    portfolio_path = tmp_path / "runtime_portfolio_state.json"

    assert result["status"] in {"OK", "AMBER"}
    assert not account_path.exists()

    # Suppressing account publication must not suppress unrelated
    # canonical runtime artifacts.
    assert session_path.exists()
    assert portfolio_path.exists()


def test_r89_publish_account_false_preserves_existing_account_mtime(
    tmp_path: Path,
    publisher_module,
) -> None:
    account_path = tmp_path / "css_account_state_pcnrass.json"

    stale_payload = {
        "status": "AVAILABLE",
        "broker": "QUESTRADE",
        "source": "QUESTRADE_LAST_KNOWN_READ_ONLY",
        "timestamp": "2026-09-07T01:00:00+00:00",
        "advisory_only": True,
        "execution_allowed": False,
    }

    account_path.write_text(
        json.dumps(stale_payload),
        encoding="utf-8",
    )

    old_time = (
        datetime.now(timezone.utc) - timedelta(minutes=20)
    ).timestamp()

    os.utime(account_path, (old_time, old_time))
    before = account_path.stat().st_mtime_ns

    publisher_module.RuntimeArtifactPublisher(
        artifacts_dir=tmp_path
    ).publish(
        runtime_cycle=8,
        runtime_portfolio_state=_runtime_state(),
        publish_account_state=False,
        timestamp="2026-09-07T03:10:00+00:00",
    )

    after = account_path.stat().st_mtime_ns

    assert after == before

    persisted = json.loads(
        account_path.read_text(encoding="utf-8")
    )

    assert persisted == stale_payload


def test_r89_fresh_helper_uses_strict_cache_read_only(
    monkeypatch,
    launcher_module,
) -> None:
    fresh = _fresh_questrade_snapshot()

    calls = {
        "read": 0,
        "read_last_known": 0,
    }

    def strict_read():
        calls["read"] += 1
        return fresh

    def forbidden_last_known():
        calls["read_last_known"] += 1
        raise AssertionError(
            "R8.9 freshness helper must not call read_last_known()"
        )

    monkeypatch.setattr(
        launcher_module._QUESTRADE_MISSION_CONTROL_CACHE,
        "read",
        strict_read,
    )

    monkeypatch.setattr(
        launcher_module._QUESTRADE_MISSION_CONTROL_CACHE,
        "read_last_known",
        forbidden_last_known,
    )

    account = (
        launcher_module
        ._fresh_questrade_canonical_account_state()
    )

    assert calls["read"] == 1
    assert calls["read_last_known"] == 0

    assert isinstance(account, dict)
    assert account["status"] == "AVAILABLE"
    assert account["broker"] == "QUESTRADE"
    assert account["source"] == "QUESTRADE_LIVE_READ_ONLY"

    assert account["cash"] == pytest.approx(-99.130056)
    assert account["equity"] == pytest.approx(1569.428972)
    assert account["buying_power"] == pytest.approx(3556.642978)

    assert account["advisory_only"] is True
    assert account["execution_allowed"] is False
    assert account["live_trading_blocked"] is True
    assert account["broker_execution_armed"] is False
    assert account["execution_authority"] is False
    assert account["broker_execution_enabled"] is False
    assert account["live_trading_enabled"] is False
    assert account["can_live_execute"] is False
    assert account["live_order_permission"] is False
    assert account["order_submission_status"] == "DISABLED"
    assert account["execution_scope"] == "LIVE_READ_ONLY"


def test_r89_no_fresh_cache_cannot_use_last_known(
    monkeypatch,
    launcher_module,
) -> None:
    calls = {
        "read": 0,
        "read_last_known": 0,
    }

    def strict_read():
        calls["read"] += 1
        return None

    def forbidden_last_known():
        calls["read_last_known"] += 1
        return _fresh_questrade_snapshot()

    monkeypatch.setattr(
        launcher_module._QUESTRADE_MISSION_CONTROL_CACHE,
        "read",
        strict_read,
    )

    monkeypatch.setattr(
        launcher_module._QUESTRADE_MISSION_CONTROL_CACHE,
        "read_last_known",
        forbidden_last_known,
    )

    account = (
        launcher_module
        ._fresh_questrade_canonical_account_state()
    )

    assert account is None
    assert calls["read"] == 1
    assert calls["read_last_known"] == 0


def test_r89_stale_snapshot_rejected_by_strict_helper(
    monkeypatch,
    launcher_module,
) -> None:
    stale = _fresh_questrade_snapshot()

    old = (
        datetime.now(timezone.utc)
        - timedelta(seconds=301)
    ).isoformat()

    stale["acquisition_timestamp"] = old
    stale["balances"]["acquisition_timestamp"] = old
    stale["positions"]["acquisition_timestamp"] = old

    monkeypatch.setattr(
        launcher_module._QUESTRADE_MISSION_CONTROL_CACHE,
        "read",
        lambda: stale,
    )

    account = (
        launcher_module
        ._fresh_questrade_canonical_account_state()
    )

    # Even if a malformed/test cache hands the helper aged evidence,
    # the canonical portfolio freshness gate must reject it.
    assert account is None


def test_r89_fresh_account_publication_preserves_fail_closed_flags(
    tmp_path: Path,
    publisher_module,
    launcher_module,
    monkeypatch,
) -> None:
    fresh = _fresh_questrade_snapshot()

    monkeypatch.setattr(
        launcher_module._QUESTRADE_MISSION_CONTROL_CACHE,
        "read",
        lambda: fresh,
    )

    account = (
        launcher_module
        ._fresh_questrade_canonical_account_state()
    )

    assert account is not None

    result = publisher_module.RuntimeArtifactPublisher(
        artifacts_dir=tmp_path
    ).publish(
        runtime_cycle=9,
        runtime_portfolio_state=_runtime_state(),
        account_state=account,
        publish_account_state=True,
    )

    assert result["status"] in {"OK", "AMBER"}

    persisted = json.loads(
        (
            tmp_path / "css_account_state_pcnrass.json"
        ).read_text(encoding="utf-8")
    )

    assert persisted["broker"] == "QUESTRADE"
    assert persisted["source"] == "QUESTRADE_LIVE_READ_ONLY"

    # The broker evidence timestamp must survive canonical publication.
    assert persisted["timestamp"] == account["timestamp"]

    # R8.9 must never create execution authority.
    assert persisted["advisory_only"] is True
    assert persisted["execution_allowed"] is False
    assert persisted["live_trading_blocked"] is True
    assert persisted["broker_execution_armed"] is False
def test_v8_aging_account_is_not_rewritten_for_unrelated_stale_artifact(
    monkeypatch,
):
    """
    R8.9 V8 regression:

    An AGING canonical account artifact is still valid broker evidence.

    If some unrelated critical artifact becomes STALE, generic runtime
    publication must continue, but it must NOT rewrite the canonical
    account artifact merely to refresh its filesystem mtime.

    Only strict fresh Questrade cache evidence may create/update the
    canonical account artifact.
    """
    import importlib.util
    import inspect
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    candidate = (
        root
        / "launcher"
        / "css_mobile_launcher.py"
    )

    assert candidate.exists()

    module_name = (
        "css_mobile_launcher_r89_v8_behavioral_regression"
    )

    spec = importlib.util.spec_from_file_location(
        module_name,
        candidate,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)

    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)

        calls = []

        freshness_feed = {
            "status": "OK",
            "artifacts": {
                "account_state": {
                    "freshness": "AGING",
                    "status": "AGING",
                },
                "session_state": {
                    "freshness": "STALE",
                    "status": "STALE",
                },
                "supervisor_state": {
                    "freshness": "FRESH",
                    "status": "FRESH",
                },
            },
        }

        def fake_freshness_feed(*args, **kwargs):
            return freshness_feed

        def fake_publish_runtime_artifacts(
            *args,
            **kwargs,
        ):
            calls.append(dict(kwargs))
            return {
                "status": "PUBLISHED",
                "test": True,
            }

        def forbidden_fresh_account_helper():
            raise AssertionError(
                "strict Questrade helper must not be called "
                "for an AGING account artifact"
            )

        monkeypatch.setattr(
            module,
            "get_runtime_artifact_freshness_feed",
            fake_freshness_feed,
        )

        monkeypatch.setattr(
            module,
            "publish_runtime_artifacts",
            fake_publish_runtime_artifacts,
        )

        monkeypatch.setattr(
            module,
            "_fresh_questrade_canonical_account_state",
            forbidden_fresh_account_helper,
        )

        # Supply explicit non-empty values where the installed
        # function accepts them, avoiding unrelated feed builders.
        sig = inspect.signature(
            module.ensure_runtime_artifacts_current
        )

        candidate_kwargs = {
            "inputs": {
                "r89_v8_test": True,
            },
            "portfolio_decision": {
                "status": "TEST",
            },
            "runtime_advisory_snapshot": {
                "status": "TEST",
            },
            "validation_summary": {
                "status": "TEST",
            },
        }

        kwargs = {
            key: value
            for key, value in candidate_kwargs.items()
            if key in sig.parameters
        }

        result = (
            module.ensure_runtime_artifacts_current(
                **kwargs
            )
        )

        # The unrelated stale artifact still requires generic
        # runtime publication.
        assert len(calls) == 1

        publication = calls[0]

        # Core V8 invariant:
        # AGING account evidence must not be rewritten merely because
        # session_state is stale.
        assert (
            publication.get("publish_account_state")
            is False
        )

        # No synthetic/reconstructed account payload should be passed.
        assert (
            publication.get("account_state")
            is None
        )

        # Function itself should complete normally.
        assert isinstance(result, dict)

        # Safety authority must never be created by reconciliation.
        if "execution_allowed" in result:
            assert result["execution_allowed"] is False

        if "advisory_only" in result:
            assert result["advisory_only"] is True

    finally:
        sys.modules.pop(module_name, None)
