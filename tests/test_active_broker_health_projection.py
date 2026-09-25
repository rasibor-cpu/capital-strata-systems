from __future__ import annotations

from dashboard.mission_control.contracts import _brokers


def test_active_broker_projects_runtime_broker_health():
    runtime_snapshot = {
        "runtime_status": "ONLINE",
        "broker": {
            "selected_broker": "COINBASE",
            "broker_mode": "paper",
            "broker_health": "RED",
            "transport": "FAIL",
            "authentication": "FAIL",
            "failure_reason": "CONNECTION_FAILED",
            "execution_scope": "READ_ONLY",
        },
    }

    result = _brokers(
        {
            "selected_broker": "COINBASE",
            "broker_health": "",
            "connection_status": "FAIL",
        },
        runtime_snapshot,
    )

    active = result["active_broker"]
    assert active["selected_broker"] == "COINBASE"
    assert active["broker_health"] == "RED"
    assert active["connection_status"] == "FAIL"
    assert active["failure_reason"] == "CONNECTION_FAILED"


def test_active_broker_legacy_health_is_only_fallback():
    runtime_snapshot = {
        "runtime_status": "ONLINE",
        "broker": {
            "selected_broker": "OANDA",
            "broker_mode": "paper",
            "transport": "PASS",
            "authentication": "PASS",
            "execution_scope": "READ_ONLY",
        },
    }

    result = _brokers(
        {
            "selected_broker": "OANDA",
            "broker_health": "GREEN",
        },
        runtime_snapshot,
    )

    assert result["active_broker"]["broker_health"] == "GREEN"
