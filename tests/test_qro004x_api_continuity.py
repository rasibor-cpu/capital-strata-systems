from dashboard.runtime.api_bridge import create_app, get_continuity_payload, get_mission_control_payload
from dashboard.runtime.dashboard_state import DashboardState


def test_api_and_mission_control_use_same_continuity_projection():
    continuity = {
        "provider": "REPLAY",
        "account_masked": "**********-001",
        "snapshot_id": "snapshot-1",
        "snapshot_source": "REPLAY",
        "snapshot_status": "CURRENT_FRESH",
        "snapshot_age_seconds": 0,
        "last_successful_sync_utc": "2026-09-11T12:00:00+00:00",
        "last_observation_utc": "2026-09-11T12:00:00+00:00",
        "ledger_status": "AVAILABLE",
        "ledger_entry_count": 1,
        "freshness": "FRESH",
        "broker_health": "HEALTHY",
        "reconciliation_status": "MATCH",
        "open_reconciliation_count": 0,
        "highest_reconciliation_severity": "info",
        "duplicate_observation_count": 0,
        "last_provider_recovery_utc": None,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    state = DashboardState()
    state.last_scan_results["broker_continuity"] = continuity
    provider = lambda: state
    api_state = get_continuity_payload(provider)
    mission = get_mission_control_payload(provider)
    assert mission["continuity"] == api_state
    assert mission["continuity"]["snapshot_id"] == "snapshot-1"
    assert mission["continuity"]["snapshot_source"] == "REPLAY"
    assert mission["continuity"]["execution_allowed"] is False


def test_primary_api_exposes_continuity_route():
    assert "/api/v1/broker-continuity" in create_app(lambda: DashboardState()).openapi()["paths"]
