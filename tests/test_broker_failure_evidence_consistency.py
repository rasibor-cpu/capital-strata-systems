from __future__ import annotations

from backend.runtime.broker_operational_status import build_broker_operational_status
from backend.runtime.canonical_runtime_snapshot import _broker_snapshot


def test_failed_connection_produces_real_failure_reason():
    result = build_broker_operational_status(
        {
            "broker": "COINBASE",
            "connection_status": "FAIL",
            "account_sync_status": "PENDING",
            "market_data_status": "PENDING",
        }
    )

    assert result["failure_reason"] == "CONNECTION_FAILED"
    assert result["legacy_operational_state"] == "DEGRADED"
    assert result["operational_state"] != "READ_ONLY_READY"


def test_connection_error_is_preserved_as_failure_reason():
    result = build_broker_operational_status(
        {
            "broker": "COINBASE",
            "connection_status": "FAIL",
            "connection_error": "provider timeout",
        }
    )

    assert result["failure_reason"] == "PROVIDER TIMEOUT"


def test_canonical_snapshot_cannot_show_failed_transport_with_blank_health():
    result = _broker_snapshot(
        {
            "selected_broker": "COINBASE",
            "connection_status": "FAIL",
            "broker_health": "",
            "connection_error": "",
        },
        {},
    )

    assert result["transport"] == "FAIL"
    assert result["broker_health"] == "RED"
    assert result["failure_reason"] == "CONNECTION_FAILED"
