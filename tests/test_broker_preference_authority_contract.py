from __future__ import annotations

from dashboard.mission_control.contracts import _safe_operator_broker_selection


def test_operator_broker_selection_forces_fail_closed_authority():
    projected = _safe_operator_broker_selection(
        {
            "selected_broker": "OANDA",
            "broker_mode": "LIVE_READ_ONLY",
            "confirmed": True,
            "execution_allowed": True,
            "live_trading_blocked": False,
            "broker_execution_armed": True,
            "runtime_activation_changed": True,
        }
    )

    assert projected["selected_broker"] == "OANDA"
    assert projected["broker_mode"] == "LIVE_READ_ONLY"
    assert projected["confirmed"] is True
    assert projected["preference_only"] is True
    assert projected["runtime_activation_changed"] is False
    assert projected["execution_allowed"] is False
    assert projected["live_trading_blocked"] is True
    assert projected["broker_execution_armed"] is False
    assert projected["advisory_only"] is True


def test_invalid_broker_preference_does_not_become_runtime_identity():
    projected = _safe_operator_broker_selection(
        {
            "selected_broker": "UNKNOWN_BROKER",
            "broker_mode": "LIVE",
            "confirmed": True,
        }
    )

    assert projected["selected_broker"] is None
    assert projected["broker_mode"] is None
    assert projected["preference_only"] is True
    assert projected["execution_allowed"] is False
    assert projected["broker_execution_armed"] is False
