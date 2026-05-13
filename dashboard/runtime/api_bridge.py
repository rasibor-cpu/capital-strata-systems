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
from dashboard.runtime.broker_adapter_conformance import (
    build_broker_adapter_conformance_payload,
)
from dashboard.runtime.broker_live_dry_run_certification import (
    build_broker_live_dry_run_certification_payload,
)
from dashboard.runtime.alerting_layer import build_alert_payload
from dashboard.runtime.deployment_profiles import get_deployment_profiles
from dashboard.runtime.live_credential_attestation import (
    build_live_credential_attestation_payload,
)
from dashboard.runtime.trade_lifecycle_replay_viewer import (
    get_trade_lifecycle_replay_payload,
)
from dashboard.runtime.ws_bridge import create_ws_router


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


def get_broker_adapter_conformance_payload() -> dict[str, Any]:
    return build_broker_adapter_conformance_payload()


def get_broker_live_dry_run_certification_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    return build_broker_live_dry_run_certification_payload(state.to_dict())


def get_live_credential_attestation_payload() -> dict[str, Any]:
    return build_live_credential_attestation_payload()


def get_alert_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_alert_payload(get_frontend_payload(state_provider))


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

    @router.get("/api/v1/broker-adapter-conformance")
    def read_broker_adapter_conformance() -> dict[str, Any]:
        return get_broker_adapter_conformance_payload()

    @router.get("/api/v1/broker-live-dry-run-certification")
    def read_broker_live_dry_run_certification() -> dict[str, Any]:
        return get_broker_live_dry_run_certification_payload(state_provider)

    @router.get("/api/v1/live-credential-attestation")
    def read_live_credential_attestation() -> dict[str, Any]:
        return get_live_credential_attestation_payload()

    @router.get("/api/v1/alerts")
    def read_alerts() -> dict[str, Any]:
        return get_alert_payload(state_provider)

    @router.get("/api/v1/deployment-profiles")
    def read_deployment_profiles() -> dict[str, Any]:
        return get_deployment_profiles()

    @router.get("/api/v1/trade-lifecycle-replay")
    def read_trade_lifecycle_replay(
        event_type: str = "",
        symbol: str = "",
        asset_class: str = "",
        cycle: str = "",
        correlation_id: str = "",
        subsystem: str = "",
        start_utc: str = "",
        end_utc: str = "",
        limit: int = 250,
    ) -> dict[str, Any]:
        return get_trade_lifecycle_replay_payload(
            event_type=event_type,
            symbol=symbol,
            asset_class=asset_class,
            cycle=cycle,
            correlation_id=correlation_id,
            subsystem=subsystem,
            start_utc=start_utc,
            end_utc=end_utc,
            limit=limit,
        )

    return router


def create_app(
    state_provider: DashboardStateProvider | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Capital Strata Systems Dashboard Runtime API",
        version="0.1.0",
    )
    app.include_router(create_dashboard_state_router(state_provider))
    app.include_router(create_ws_router(state_provider))
    return app


app = create_app()


__all__ = [
    "DashboardStateProvider",
    "app",
    "create_app",
    "create_dashboard_state_router",
    "default_dashboard_state_provider",
    "get_broker_adapter_conformance_payload",
    "get_broker_live_dry_run_certification_payload",
    "get_broker_reconciliation_payload",
    "get_alert_payload",
    "get_dashboard_state_payload",
    "get_frontend_payload",
    "get_live_credential_attestation_payload",
    "get_trade_lifecycle_replay_payload",
]
