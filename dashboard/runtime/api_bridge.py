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
from backend.validation.live_readiness_certification import (
    live_readiness_blocker_diagnostics,
)
from backend.analytics.broker_performance_confidence import (
    build_broker_performance_confidence_report,
)
from backend.analytics.opportunity_intelligence_engine import (
    build_opportunity_intelligence_report,
)
from backend.analytics.capital_allocation_optimizer import (
    build_capital_allocation_intelligence_report,
)
from backend.runtime.runtime_certification_snapshot import (
    runtime_certification_diagnostics,
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


def get_broker_read_only_status_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "broker",
    )


def get_startup_diagnostics_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    broker_payload = get_broker_read_only_status_payload(state_provider)
    broker_data = broker_payload.get("data", {})
    broker_data = broker_data if isinstance(broker_data, dict) else {}
    return {
        **broker_payload,
        "section": "startup_diagnostics",
        "data": broker_data.get("startup_diagnostics", {}),
        "advisory_only": True,
        "execution_allowed": False,
    }


def get_live_readiness_state_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    broker_payload = get_broker_read_only_status_payload(state_provider)
    broker_data = broker_payload.get("data", {})
    broker_data = broker_data if isinstance(broker_data, dict) else {}
    return {
        **broker_payload,
        "section": "live_readiness_state",
        "data": {
            "readiness_state": broker_data.get("readiness_state", "UNCONFIGURED"),
            "go_no_go": broker_data.get("go_no_go", "NO GO"),
            "readiness_checklist": broker_data.get("readiness_checklist", []),
            "startup_diagnostics": broker_data.get("startup_diagnostics", {}),
        },
        "advisory_only": True,
        "execution_allowed": False,
    }


def get_live_execution_authority_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    broker_payload = get_broker_read_only_status_payload(state_provider)
    broker_data = broker_payload.get("data", {})
    broker_data = broker_data if isinstance(broker_data, dict) else {}
    return {
        **broker_payload,
        "section": "live_execution_authority",
        "data": {
            "operator_requested_live": broker_data.get("operator_requested_live", False),
            "execution_authority": broker_data.get("execution_authority", False),
            "authority_reason": broker_data.get("authority_reason", "Operator Intent Missing"),
            "live_authority_state": broker_data.get("live_authority_state", "BLOCKED"),
            "can_live_execute": broker_data.get("can_live_execute", False),
            "live_execution_authority": broker_data.get("live_execution_authority", {}),
        },
        "advisory_only": True,
        "execution_allowed": False,
    }


def get_broker_readiness_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    broker_payload = get_broker_read_only_status_payload(state_provider)
    broker_data = broker_payload.get("data", {})
    broker_data = broker_data if isinstance(broker_data, dict) else {}
    return {
        **broker_payload,
        "section": "broker_readiness",
        "data": broker_data.get("broker_readiness", {}),
        "advisory_only": True,
        "execution_allowed": False,
    }


def get_broker_credential_diagnostics_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "broker_credential_diagnostics",
    )


def get_broker_parity_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "broker_parity",
    )


def get_coinbase_live_validation_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "coinbase_live_validation",
    )


def get_oanda_live_validation_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "oanda_live_validation",
    )


def get_broker_operational_status_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "broker_operational_status",
    )


def get_runtime_certification_snapshot_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "runtime_certification_snapshot",
    )


def get_runtime_certification_diagnostics_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    snapshot_payload = get_runtime_certification_snapshot_payload(state_provider)
    snapshot = snapshot_payload.get("data", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    return {
        **snapshot_payload,
        "section": "runtime_certification_diagnostics",
        "data": runtime_certification_diagnostics(snapshot),
        "advisory_only": True,
        "execution_allowed": False,
    }


def get_rc1_operational_dashboard_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    return build_section_payload(
        _state_from_provider(state_provider),
        "rc1_operational_dashboard",
    )


def get_broker_performance_intelligence_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    report = build_broker_performance_confidence_report(state.to_dict())
    return {
        "payload_version": "1.0.0",
        "payload_schema": "css.broker.performance_intelligence.v1",
        "generated_at": report["generated_at"],
        "section": "broker_performance_intelligence",
        "data": report,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_enabled": False,
    }


def get_opportunity_intelligence_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    report = build_opportunity_intelligence_report(state.to_dict())
    return {
        "payload_version": "1.0.0",
        "payload_schema": "css.opportunity_intelligence.v1",
        "generated_at": report["generated_at"],
        "section": "opportunity_intelligence",
        "advisory_only": True,
        "execution_allowed": False,
        "data": report,
        "opportunities": report["opportunities"],
        "leaderboard": report["leaderboard"],
    }


def get_capital_allocation_intelligence_payload(
    state_provider: DashboardStateProvider | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    report = build_capital_allocation_intelligence_report(state.to_dict())
    return {
        "payload_version": "1.0.0",
        "payload_schema": "css.capital_allocation_intelligence.v1",
        "generated_at": report["generated_at"],
        "section": "capital_allocation_intelligence",
        "advisory_only": True,
        "execution_allowed": False,
        "data": report,
        "capital_plan": report["allocation_plan"],
        "allocation_summary": report["allocation_summary"],
        "portfolio_metrics": report["portfolio_metrics"],
        "recommendations": report["recommendations"],
        "warnings": report["warnings"],
    }


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

    @router.get("/api/v1/opportunity-intelligence")
    def read_opportunity_intelligence() -> dict[str, Any]:
        return get_opportunity_intelligence_payload(state_provider)

    @router.get("/api/v1/capital-allocation-intelligence")
    def read_capital_allocation_intelligence() -> dict[str, Any]:
        return get_capital_allocation_intelligence_payload(state_provider)

    @router.get("/api/v1/trade-summary")
    def read_trade_summary() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "trade_summary",
        )

    @router.get("/api/v1/session-command-centre")
    def read_session_command_centre() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "session_command_centre",
        )

    @router.get("/api/v1/live-micro-pilot-status")
    def read_live_micro_pilot_status() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "live_micro_pilot",
        )

    @router.get("/api/v1/live-readiness-certification")
    def read_live_readiness_certification() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "live_readiness_certification",
        )

    @router.get("/api/v1/live-readiness-blockers")
    def read_live_readiness_blockers() -> dict[str, Any]:
        return live_readiness_blocker_diagnostics()

    @router.get("/api/v1/broker")
    def read_broker() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "broker",
        )

    @router.get("/api/v1/broker-read-only-status")
    def read_broker_read_only_status() -> dict[str, Any]:
        return get_broker_read_only_status_payload(state_provider)

    @router.get("/api/v1/startup-diagnostics")
    def read_startup_diagnostics() -> dict[str, Any]:
        return get_startup_diagnostics_payload(state_provider)

    @router.get("/api/v1/live-readiness-state")
    def read_live_readiness_state() -> dict[str, Any]:
        return get_live_readiness_state_payload(state_provider)

    @router.get("/api/v1/live-execution-authority")
    def read_live_execution_authority() -> dict[str, Any]:
        return get_live_execution_authority_payload(state_provider)

    @router.get("/api/v1/broker-readiness")
    def read_broker_readiness() -> dict[str, Any]:
        return get_broker_readiness_payload(state_provider)

    @router.get("/api/v1/broker-credential-diagnostics")
    def read_broker_credential_diagnostics() -> dict[str, Any]:
        return get_broker_credential_diagnostics_payload(state_provider)

    @router.get("/api/v1/broker-parity")
    def read_broker_parity() -> dict[str, Any]:
        return get_broker_parity_payload(state_provider)

    @router.get("/api/v1/coinbase-live-read-only-validation")
    def read_coinbase_live_read_only_validation() -> dict[str, Any]:
        return get_coinbase_live_validation_payload(state_provider)

    @router.get("/api/v1/oanda-live-read-only-validation")
    def read_oanda_live_read_only_validation() -> dict[str, Any]:
        return get_oanda_live_validation_payload(state_provider)

    @router.get("/api/v1/broker-operational-status")
    def read_broker_operational_status() -> dict[str, Any]:
        return get_broker_operational_status_payload(state_provider)

    @router.get("/api/v1/runtime-certification-snapshot")
    def read_runtime_certification_snapshot() -> dict[str, Any]:
        return get_runtime_certification_snapshot_payload(state_provider)

    @router.get("/api/v1/runtime-certification-diagnostics")
    def read_runtime_certification_diagnostics() -> dict[str, Any]:
        return get_runtime_certification_diagnostics_payload(state_provider)

    @router.get("/api/v1/rc1-operational-dashboard")
    def read_rc1_operational_dashboard() -> dict[str, Any]:
        return get_rc1_operational_dashboard_payload(state_provider)

    @router.get("/api/v1/broker-performance-intelligence")
    def read_broker_performance_intelligence() -> dict[str, Any]:
        return get_broker_performance_intelligence_payload(state_provider)

    @router.get("/api/v1/broker-reconciliation")
    def read_broker_reconciliation() -> dict[str, Any]:
        return build_section_payload(
            _state_from_provider(state_provider),
            "broker_reconciliation",
        )

    return router


def create_app(
    state_provider: DashboardStateProvider | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Capital Strata Systems Dashboard Runtime API",
        version="0.1.0",
    )

    dashboard_router = create_dashboard_state_router(state_provider)
    ws_router = create_ws_router(state_provider)

    for route in dashboard_router.routes:
        app.router.routes.append(route)

    for route in ws_router.routes:
        app.router.routes.append(route)

    return app


app = create_app()


__all__ = [
    "DashboardStateProvider",
    "app",
    "create_app",
    "create_dashboard_state_router",
    "default_dashboard_state_provider",
    "get_broker_read_only_status_payload",
    "get_broker_parity_payload",
    "get_broker_operational_status_payload",
    "get_runtime_certification_snapshot_payload",
    "get_runtime_certification_diagnostics_payload",
    "get_rc1_operational_dashboard_payload",
    "get_broker_performance_intelligence_payload",
    "get_broker_credential_diagnostics_payload",
    "get_broker_readiness_payload",
    "get_broker_reconciliation_payload",
    "get_coinbase_live_validation_payload",
    "get_oanda_live_validation_payload",
    "get_dashboard_state_payload",
    "get_frontend_payload",
    "get_opportunity_intelligence_payload",
    "get_capital_allocation_intelligence_payload",
    "get_live_execution_authority_payload",
    "get_live_readiness_state_payload",
    "get_startup_diagnostics_payload",
]
