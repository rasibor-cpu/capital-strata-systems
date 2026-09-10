from datetime import datetime, timedelta, timezone

from dashboard.runtime.runtime_heartbeat import (
    read_runtime_heartbeat,
    start_runtime_heartbeat,
)
from dashboard.runtime.runtime_operational_state import (
    HEALTHY,
    NOT_APPLICABLE,
    build_runtime_operational_state,
)


def test_runtime_heartbeat_source_produces_temporal_evidence():
    start_runtime_heartbeat(interval_seconds=60.0)
    heartbeat = read_runtime_heartbeat()

    assert heartbeat["heartbeat_at"]
    state = build_runtime_operational_state(
        {
            "process_alive": True,
            "api_health": "HEALTHY",
            "supervisor_status": "UNKNOWN",
            "broker_data_freshness": NOT_APPLICABLE,
            **heartbeat,
        }
    )
    assert state.heartbeat_status == HEALTHY
    assert state.execution_allowed is False


def test_missing_supervisor_evidence_stays_unknown_and_brokerless_reason_is_explicit():
    state = build_runtime_operational_state(
        {
            "process_alive": True,
            "api_health": "HEALTHY",
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "supervisor_status": "UNKNOWN",
            "broker_data_freshness": NOT_APPLICABLE,
            "broker_freshness_reason": "SIMULATED_PAPER_RUNTIME_HAS_NO_LIVE_BROKER_SNAPSHOT",
        }
    )

    assert state.supervisor_status == "UNKNOWN"
    assert state.broker_data_freshness == NOT_APPLICABLE
    assert state.runtime_status == "DEGRADED"
    assert state.unattended_ready is False