from dashboard.runtime.api_bridge import get_caie_shadow_payload
from dashboard.runtime.dashboard_state import DashboardState


def test_missing_caie_shadow_data_has_safe_fallback():
    state = DashboardState()
    payload = get_caie_shadow_payload(lambda: state)
    assert payload["status"] == "UNAVAILABLE"
    assert payload["reason"] == "NO_CAIE_SHADOW_DATA"
    assert payload["allocations"] == []
    assert payload["mode"] == "SHADOW_ONLY"
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["live_trading_authorized"] is False


def test_existing_caie_shadow_payload_is_projected_read_only():
    state = DashboardState(
        last_scan_results={
            "caie_shadow": {
                "schema_version": "css.caie.shadow-runtime.v1",
                "status": "AVAILABLE",
                "reason": "CAIE_SHADOW_PLAN_READY",
                "allocations": [
                    {
                        "proposal_id": "opp-1",
                        "symbol": "AAPL",
                        "allocated_capital": "250",
                    }
                ],
                "execution_allowed": True,
                "broker_execution_armed": True,
                "money_movement_allowed": True,
                "live_trading_authorized": True,
            }
        }
    )
    payload = get_caie_shadow_payload(lambda: state)
    assert payload["status"] == "AVAILABLE"
    assert len(payload["allocations"]) == 1
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["live_trading_authorized"] is False
    assert payload["mode"] == "SHADOW_ONLY"


def test_caie_api_route_exists_on_runtime_router():
    from dashboard.runtime.api_bridge import create_dashboard_state_router

    paths = {getattr(route, "path", None) for route in create_dashboard_state_router(lambda: DashboardState()).routes}
    assert "/api/v1/caie-shadow" in paths
