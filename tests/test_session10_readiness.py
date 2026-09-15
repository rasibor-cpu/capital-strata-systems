from backend.brokers.session10_readiness import (
    FAILED_CLOSED,
    LIVE_READ_VALIDATED,
    READY_BLOCKED_EXTERNAL,
    build_session10_readiness,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_state import DashboardState


def mission(**changes):
    payload = {
        "broker_name": "QUESTRADE",
        "broker_connected": False,
        "broker_authenticated": False,
        "data_freshness": "UNAVAILABLE",
        "capital_provenance": "UNKNOWN",
        "state_complete": False,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "read_only": True,
    }
    payload.update(changes)
    return payload


def continuity(**changes):
    payload = {
        "snapshot_status": "UNAVAILABLE",
        "ledger_status": "UNAVAILABLE",
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "read_only": True,
    }
    payload.update(changes)
    return payload


def test_structurally_ready_but_external_auth_blocked_is_not_live_validated():
    result = build_session10_readiness(mission(), continuity())

    assert result["status"] == READY_BLOCKED_EXTERNAL
    assert result["software_structural_readiness"] is True
    assert result["real_account_validation"] is False
    assert result["external_blocker"] == (
        "BLOCKED_EXTERNAL_403_CLOUDFLARE_1010"
    )
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True


def test_authenticated_current_real_broker_still_requires_explicit_evidence():
    live_state = mission(
        broker_connected=True,
        broker_authenticated=True,
        data_freshness="CURRENT",
        capital_provenance="REAL_BROKER",
        state_complete=True,
    )

    result = build_session10_readiness(
        live_state,
        continuity(snapshot_status="CURRENT", ledger_status="AVAILABLE"),
        live_validation_evidence=False,
    )

    assert result["status"] == READY_BLOCKED_EXTERNAL
    assert result["real_account_validation"] is False


def test_explicit_live_evidence_can_validate_only_safe_complete_read_state():
    live_state = mission(
        broker_connected=True,
        broker_authenticated=True,
        data_freshness="CURRENT",
        capital_provenance="REAL_BROKER",
        state_complete=True,
    )

    result = build_session10_readiness(
        live_state,
        continuity(snapshot_status="CURRENT", ledger_status="AVAILABLE"),
        live_validation_evidence=True,
    )

    assert result["status"] == LIVE_READ_VALIDATED
    assert result["real_account_validation"] is True
    assert result["external_blocker"] is None
    assert result["execution_allowed"] is False


def test_corrupt_continuity_fails_closed_even_with_live_evidence():
    live_state = mission(
        broker_connected=True,
        broker_authenticated=True,
        data_freshness="CURRENT",
        capital_provenance="REAL_BROKER",
        state_complete=True,
    )

    result = build_session10_readiness(
        live_state,
        continuity(snapshot_status="CORRUPT", ledger_status="AVAILABLE"),
        live_validation_evidence=True,
    )

    assert result["status"] == FAILED_CLOSED
    assert result["real_account_validation"] is False


def test_any_execution_authority_breaks_structural_readiness():
    result = build_session10_readiness(
        mission(execution_allowed=True),
        continuity(),
    )

    assert result["status"] == FAILED_CLOSED
    assert result["software_structural_readiness"] is False
    assert result["execution_allowed"] is False


def test_api_exposes_same_session10_readiness_surface_to_web_and_phone_clients():
    app = create_app(lambda: DashboardState())
    paths = set(app.openapi()["paths"])

    assert "/api/v1/session10-readiness" in paths
    operations = app.openapi()["paths"]["/api/v1/session10-readiness"]
    assert set(operations) == {"get"}
