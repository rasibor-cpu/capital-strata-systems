from __future__ import annotations

from launcher.css_mobile_launcher import _resolve_runtime_broker_identity


def test_runtime_broker_comes_from_startup_not_operator_preference_session():
    session = {
        "selected_broker": "OANDA",
        "broker_mode": "LIVE_READ_ONLY",
        "broker_preference_only": True,
    }
    broker_startup = {
        "selected_broker": "COINBASE",
        "broker_mode": "paper",
    }
    runtime_mode_resolution = {"broker_mode": "paper"}

    broker, mode, startup_matches = _resolve_runtime_broker_identity(
        session,
        broker_startup,
        runtime_mode_resolution,
    )

    assert broker == "COINBASE"
    assert mode == "paper"
    assert startup_matches is True


def test_preference_only_session_does_not_create_runtime_active_broker():
    session = {
        "selected_broker": "QUESTRADE",
        "broker_mode": "LIVE_READ_ONLY",
        "broker_preference_only": True,
    }

    broker, mode, startup_matches = _resolve_runtime_broker_identity(
        session,
        {},
        {},
    )

    assert broker == "NONE"
    assert mode == "unresolved"
    assert startup_matches is False


def test_legacy_non_preference_session_can_supply_runtime_identity_when_startup_missing():
    session = {
        "selected_broker": "OANDA",
        "broker_mode": "live",
        "broker_preference_only": False,
    }

    broker, mode, startup_matches = _resolve_runtime_broker_identity(
        session,
        {},
        {},
    )

    assert broker == "OANDA"
    assert mode == "live"
    assert startup_matches is False
