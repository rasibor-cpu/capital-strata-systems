from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, FastAPI

from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import (
    build_frontend_payload,
    build_section_payload,
)
from dashboard.runtime.broker_balance_reconciliation import (
    build_broker_reconciliation_payload,
)
from dashboard.runtime.ws_bridge import create_ws_router
from dashboard.runtime.mission_control_state import build_mission_control_state
from backend.brokers.continuity_projection import build_continuity_state
from dashboard.runtime.runtime_operational_state import (
    build_runtime_operational_state,
)
from dashboard.runtime.runtime_health_provider import read_runtime_health_snapshot
from dashboard.runtime.broker_live_dry_run_certification import build_from_dashboard_state
from dashboard.runtime.broker_adapter_conformance import build_broker_adapter_conformance_payload
from dashboard.runtime.live_credential_attestation import (
    attest_live_credentials,
    build_live_credential_attestation_payload,
)


DashboardStateProvider = Callable[[], DashboardState]


def default_dashboard_state_provider() -> DashboardState:
    """
    Build an empty-safe DashboardState for API smoke and shadow-mode wiring.

    Live payload sources should inject their own provider instead of changing
    runtime bootstrap behavior during migration.
    """

    return DashboardHydrationCoordinator().hydrate()


def _state_from_provider(
    state_provider: DashboardStateProvider | None = None,
) -> DashboardState:
    provider = state_provider or default_dashboard_state_provider
    state = provider()

    if not isinstance(state, DashboardState):
        raise TypeError("dashboard state provider must return DashboardState")

    return state


def get_dashboard_state_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return _state_from_provider(state_provider).to_dict()


def get_frontend_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_frontend_payload(_state_from_provider(state_provider))


def get_broker_reconciliation_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    return build_broker_reconciliation_payload(state.to_dict())


def get_mission_control_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    payload = state.to_dict()
    account = payload.get("account_summary", {})
    broker = payload.get("broker_summary", {})
    broker_payload = {
        **broker,
        "broker_name": broker.get("selected_broker", "UNKNOWN"),
        "account_mode": broker.get("broker_mode", "UNKNOWN"),
        "broker_connected": broker.get("connected", False),
        "account": broker.get("account_snapshot", {}),
        "positions": broker.get("position_snapshot"),
        "balances": account,
        "execution_allowed": False,
        "evidence_refs": ["DashboardState.broker_state", "DashboardState.account_summary"],
    }
    mission = build_mission_control_state(
        broker_payload,
        local_account=account,
        local_positions=payload.get("position_state", {}).get("positions", []),
    ).as_dict()
    mission["continuity"] = get_continuity_payload(state_provider)
    mission["runtime_operational_state"] = get_runtime_health_payload(state_provider)
    return mission


def get_continuity_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    continuity = state.last_scan_results.get("broker_continuity")
    if isinstance(continuity, dict):
        return dict(continuity)
    return build_continuity_state(None)


def get_runtime_health_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    snapshot = state.last_scan_results.get("runtime_operational_state")
    if not isinstance(snapshot, dict):
        snapshot = state.last_scan_results.get("runtime_health", {})
    if not snapshot:
        snapshot = read_runtime_health_snapshot(
            broker_mode=state.broker_state.broker_mode,
            broker_name=state.broker_state.selected_broker,
        )
    return build_runtime_operational_state(snapshot).as_dict()


def get_runtime_alerts_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    health = get_runtime_health_payload(state_provider)
    alerts = health.get("alerts", [])
    return {
        "read_only": True,
        "generated_utc": health.get("assessed_at"),
        "total_returned": len(alerts),
        "alerts": alerts,
    }


def get_broker_live_dry_run_certification_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    payload = state.to_dict()
    broker = payload.get("broker_summary", {})
    selected_broker = str(
        broker.get("selected_broker")
        or broker.get("broker_name")
        or "NONE"
    ).strip().lower()
    credential_ready = False
    if selected_broker not in {"", "none", "unknown"}:
        try:
            credential_ready = (
                attest_live_credentials(selected_broker).get("status") == "READY"
            )
        except Exception:
            credential_ready = False
    return build_from_dashboard_state(
        payload,
        credential_ready=credential_ready,
        dry_run_probe=None,
    )


def create_dashboard_state_router(
    state_provider: DashboardStateProvider | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/dashboard-state")
    def read_dashboard_state() -> dict[str, Any]:
        return get_dashboard_state_payload(state_provider)

    @router.get("/api/v1/frontend-state")
    def read_frontend_state() -> dict[str, Any]:
        return get_frontend_payload(state_provider)

    @router.get("/api/v1/account-summary")
    def read_account_summary() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "account_summary",
        )

    @router.get("/api/v1/positions")
    def read_positions() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "positions",
        )

    @router.get("/api/v1/risk")
    def read_risk() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "risk",
        )

    @router.get("/api/v1/governance")
    def read_governance() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "governance",
        )

    @router.get("/api/v1/opportunities")
    def read_opportunities() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "opportunities",
        )

    @router.get("/api/v1/broker")
    def read_broker() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "broker",
        )

    @router.get("/api/v1/broker-reconciliation")
    def read_broker_reconciliation() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "broker_reconciliation",
        )

    @router.get("/api/v1/mission-control")
    def read_mission_control() -> dict[str, Any]:
        return get_mission_control_payload(state_provider)

    @router.get("/api/v1/broker-state")
    def read_broker_state() -> dict[str, Any]:
        return get_mission_control_payload(state_provider)

    @router.get("/api/v1/broker-continuity")
    def read_broker_continuity() -> dict[str, Any]:
        return get_continuity_payload(state_provider)

    @router.get("/api/v1/questrade/account-summary")
    def read_questrade_account_summary() -> dict[str, Any]:
        payload = get_mission_control_payload(state_provider)
        if payload.get("broker_name") != "QUESTRADE":
            return {
                "status": "UNAVAILABLE",
                "reason_codes": ["BROKER_NOT_CONNECTED"],
                "read_only": True,
            }
        return payload

    @router.get("/api/v1/broker-live-dry-run-certification")
    def read_broker_live_dry_run_certification() -> dict[str, Any]:
        return get_broker_live_dry_run_certification_payload(state_provider)

    @router.get("/api/v1/broker-adapter-conformance")
    def read_broker_adapter_conformance() -> dict[str, Any]:
        return build_broker_adapter_conformance_payload()

    @router.get("/api/v1/live-credential-attestation")
    def read_live_credential_attestation() -> dict[str, Any]:
        return build_live_credential_attestation_payload()

    @router.get("/api/v1/runtime-health")
    def read_runtime_health() -> dict[str, Any]:
        return get_runtime_health_payload(state_provider)

    @router.get("/api/v1/runtime-alerts")
    def read_runtime_alerts() -> dict[str, Any]:
        return get_runtime_alerts_payload(state_provider)

    return router


def create_app(
    state_provider: DashboardStateProvider | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Capital Strata Systems Dashboard Runtime API",
        version="0.1.0",
    )
    # FastAPI/Starlette version drift in cloud CI exposed an include_router
    # compatibility issue where nested router routes were not materialized on
    # the application. Extend the application route table from the already
    # constructed read-only routers instead. This preserves the same endpoint
    # callables and does not introduce any mutation surface.
    dashboard_router = create_dashboard_state_router(state_provider)
    websocket_router = create_ws_router(state_provider)
    app.router.routes.extend(dashboard_router.routes)
    app.router.routes.extend(websocket_router.routes)
    return app


app = create_app()


__all__ = [
    "DashboardStateProvider",
    "app",
    "create_app",
    "create_dashboard_state_router",
    "default_dashboard_state_provider",
    "get_broker_reconciliation_payload",
    "get_broker_live_dry_run_certification_payload",
    "get_dashboard_state_payload",
    "get_frontend_payload",
    "get_continuity_payload",
    "get_mission_control_payload",
    "get_runtime_alerts_payload",
    "get_runtime_health_payload",
]
