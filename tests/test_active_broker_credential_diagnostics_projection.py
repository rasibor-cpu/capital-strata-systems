from __future__ import annotations

from dashboard.mission_control.contracts import _brokers


def test_active_broker_projects_only_redacted_credential_diagnostics():
    runtime_snapshot = {
        "source": "RUNTIME",
        "runtime_status": "ONLINE",
        "broker": {
            "selected_broker": "COINBASE",
            "broker_health": "RED",
            "transport": "FAIL",
            "failure_reason": "CONNECTION_FAILED",
        },
    }
    broker = {
        "selected_broker": "COINBASE",
        "broker_credential_diagnostics": {
            "credentials_present": False,
            "canonical_failure_reason": "KEY_MISSING",
            "missing_credential_fields": [
                "COINBASE_CDP_KEY_NAME|COINBASE_KEY_NAME|COINBASE_API_KEY",
                "COINBASE_CDP_PRIVATE_KEY|COINBASE_PRIVATE_KEY|COINBASE_API_SECRET|COINBASE_KEY_FILE",
            ],
            "recommended_action": "Configure the Coinbase CDP key name",
            "secret_value": "must-not-leak",
        },
    }

    active = _brokers(broker, runtime_snapshot)["active_broker"]

    assert active["credential_status"] == "MISSING"
    assert active["credential_failure_reason"] == "KEY_MISSING"
    assert len(active["missing_credential_fields"]) == 2
    assert active["credential_recommended_action"] == "Configure the Coinbase CDP key name"
    assert active["credential_values_exposed"] is False
    assert "secret_value" not in active
