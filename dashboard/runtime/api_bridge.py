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
from dashboard.runtime.coinbase_micro_live_dry_run_probe import (
    build_coinbase_micro_live_dry_run_probe_payload,
)
from dashboard.runtime.alerting_layer import build_alert_payload
from dashboard.runtime.deployment_profiles import get_deployment_profiles
from dashboard.runtime.live_credential_attestation import (
    build_live_credential_attestation_payload,
)
from dashboard.runtime.micro_live_broker_readiness_confirmation import (
    build_micro_live_broker_readiness_confirmation_payload,
)
from dashboard.runtime.micro_live_pilot_readiness import (
    build_micro_live_pilot_readiness_payload,
    load_pcnrass_validation_summary,
)
from dashboard.runtime.micro_live_operator_approval_gate import (
    build_micro_live_operator_approval_gate_payload,
)
from dashboard.runtime.micro_live_pilot_order_intent import (
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.runtime.micro_live_pre_pilot_go_no_go import (
    build_micro_live_pre_pilot_go_no_go_payload,
)
from dashboard.runtime.runtime_event_bus import (
    RuntimeEventBus,
    get_default_runtime_event_bus,
)
from dashboard.runtime.runtime_event_inspector import (
    get_runtime_event_inspection_payload,
)
from dashboard.runtime.runtime_event_persistence_policy import (
    get_runtime_event_persistence_policy_payload,
)
from dashboard.runtime.runtime_event_persistence_simulator import (
    get_runtime_event_persistence_simulation_payload,
)
from dashboard.runtime.runtime_event_persistence_scenario import (
    build_runtime_event_persistence_scenario_report,
)
from dashboard.runtime.runtime_event_persistence_report import (
    build_runtime_event_persistence_report,
)
from dashboard.runtime.runtime_event_persistence_checklist import (
    build_runtime_event_persistence_checklist,
)
from dashboard.runtime.runtime_event_persistence_checklist_export import (
    build_runtime_event_persistence_checklist_export,
)
from dashboard.runtime.runtime_event_storage_profiles import (
    get_runtime_event_storage_profiles_payload,
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


def get_runtime_events_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    export: bool = False,
) -> dict[str, Any]:
    return get_runtime_event_inspection_payload(
        event_bus or get_default_runtime_event_bus(),
        event_type=event_type,
        subsystem=subsystem,
        severity=severity,
        correlation_id=correlation_id,
        limit=limit,
        export=export,
    )


def get_runtime_event_persistence_policy_inspection_payload() -> dict[str, Any]:
    return get_runtime_event_persistence_policy_payload()


def get_runtime_event_persistence_sim_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    requested_window_minutes: int = 15,
    reason: str = "runtime event persistence dry-run simulation",
    operator_id: str = "",
    approval_token_present: bool = False,
    requested_export_format: str = "json",
) -> dict[str, Any]:
    return get_runtime_event_persistence_simulation_payload(
        event_bus or get_default_runtime_event_bus(),
        event_type=event_type,
        subsystem=subsystem,
        severity=severity,
        correlation_id=correlation_id,
        limit=limit,
        requested_window_minutes=requested_window_minutes,
        reason=reason,
        operator_id=operator_id,
        approval_token_present=approval_token_present,
        requested_export_format=requested_export_format,
    )


def get_runtime_event_persistence_scenarios_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    requested_window_minutes: int = 15,
    reason: str = "runtime event persistence dry-run scenario",
    operator_id: str = "",
    approval_token_present: bool = False,
    requested_export_format: str = "json",
) -> dict[str, Any]:
    simulation = get_runtime_event_persistence_sim_payload(
        event_bus,
        event_type=event_type,
        subsystem=subsystem,
        severity=severity,
        correlation_id=correlation_id,
        limit=limit,
        requested_window_minutes=requested_window_minutes,
        reason=reason,
        operator_id=operator_id,
        approval_token_present=approval_token_present,
        requested_export_format=requested_export_format,
    )
    return {
        "read_only": True,
        "simulation_only": True,
        "persistence_enabled": False,
        "writes_performed": False,
        "storage_profiles": get_runtime_event_storage_profiles_payload(),
        "simulation": simulation,
        "scenario_report": build_runtime_event_persistence_scenario_report(simulation),
    }


def get_runtime_event_persistence_report_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    requested_window_minutes: int = 15,
    reason: str = "runtime event persistence dry-run report",
    operator_id: str = "",
    approval_token_present: bool = False,
    requested_export_format: str = "json",
) -> dict[str, Any]:
    scenario_payload = get_runtime_event_persistence_scenarios_payload(
        event_bus,
        event_type=event_type,
        subsystem=subsystem,
        severity=severity,
        correlation_id=correlation_id,
        limit=limit,
        requested_window_minutes=requested_window_minutes,
        reason=reason,
        operator_id=operator_id,
        approval_token_present=approval_token_present,
        requested_export_format=requested_export_format,
    )
    return build_runtime_event_persistence_report(
        scenario_payload.get("simulation", {}),
        scenario_payload,
    )


def get_runtime_event_persistence_checklist_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    requested_window_minutes: int = 15,
    reason: str = "runtime event persistence operator checklist",
    operator_id: str = "",
    approval_token_present: bool = False,
    requested_export_format: str = "json",
) -> dict[str, Any]:
    report = get_runtime_event_persistence_report_payload(
        event_bus,
        event_type=event_type,
        subsystem=subsystem,
        severity=severity,
        correlation_id=correlation_id,
        limit=limit,
        requested_window_minutes=requested_window_minutes,
        reason=reason,
        operator_id=operator_id,
        approval_token_present=approval_token_present,
        requested_export_format=requested_export_format,
    )
    return build_runtime_event_persistence_checklist(report)


def get_runtime_event_persistence_checklist_export_payload(
    event_bus: RuntimeEventBus | None = None,
    *,
    event_type: str = "",
    subsystem: str = "",
    severity: str = "",
    correlation_id: str = "",
    limit: int | None = None,
    requested_window_minutes: int = 15,
    reason: str = "runtime event persistence checklist export",
    operator_id: str = "",
    approval_token_present: bool = False,
    requested_export_format: str = "json",
) -> dict[str, Any]:
    checklist = get_runtime_event_persistence_checklist_payload(
        event_bus,
        event_type=event_type,
        subsystem=subsystem,
        severity=severity,
        correlation_id=correlation_id,
        limit=limit,
        requested_window_minutes=requested_window_minutes,
        reason=reason,
        operator_id=operator_id,
        approval_token_present=approval_token_present,
        requested_export_format=requested_export_format,
    )
    return build_runtime_event_persistence_checklist_export(checklist)


def get_micro_live_pilot_readiness_payload(
    state_provider: DashboardStateProvider | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    dashboard_payload = state.to_dict()
    certification = build_broker_live_dry_run_certification_payload(dashboard_payload)
    persistence_checklist = get_runtime_event_persistence_checklist_payload(
        event_bus or get_default_runtime_event_bus(),
    )
    return build_micro_live_pilot_readiness_payload(
        dashboard_payload,
        live_readiness_certification=certification,
        persistence_checklist=persistence_checklist,
        pcnrass_summary=load_pcnrass_validation_summary(),
        operator_review_completed=False,
    )


def get_micro_live_pilot_order_intent_payload() -> dict[str, Any]:
    return build_micro_live_pilot_order_intent_payload()


def get_coinbase_micro_live_dry_run_probe_payload() -> dict[str, Any]:
    return build_coinbase_micro_live_dry_run_probe_payload(
        get_micro_live_pilot_order_intent_payload(),
    )


def get_micro_live_operator_approval_gate_payload(
    state_provider: DashboardStateProvider | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> dict[str, Any]:
    return build_micro_live_operator_approval_gate_payload(
        pilot_readiness=get_micro_live_pilot_readiness_payload(
            state_provider,
            event_bus,
        ),
        dry_run_probe=get_coinbase_micro_live_dry_run_probe_payload(),
        pcnrass_summary=load_pcnrass_validation_summary(),
        broker_readiness_confirmed=False,
        kill_switch_confirmed=False,
    )


def get_micro_live_broker_readiness_confirmation_payload(
    state_provider: DashboardStateProvider | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> dict[str, Any]:
    state = _state_from_provider(state_provider)
    pcnrass_summary = load_pcnrass_validation_summary()
    dry_run_probe = get_coinbase_micro_live_dry_run_probe_payload()
    operator_gate = get_micro_live_operator_approval_gate_payload(
        state_provider,
        event_bus,
    )
    persistence_checklist = get_runtime_event_persistence_checklist_payload(
        event_bus or get_default_runtime_event_bus(),
    )
    return build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=state.to_dict(),
        dry_run_probe=dry_run_probe,
        operator_approval_gate=operator_gate,
        persistence_checklist=persistence_checklist,
        pcnrass_summary=pcnrass_summary,
    )


def get_micro_live_pre_pilot_go_no_go_payload(
    state_provider: DashboardStateProvider | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> dict[str, Any]:
    pcnrass_summary = load_pcnrass_validation_summary()
    pilot_readiness = get_micro_live_pilot_readiness_payload(
        state_provider,
        event_bus,
    )
    order_intent = get_micro_live_pilot_order_intent_payload()
    dry_run_probe = get_coinbase_micro_live_dry_run_probe_payload()
    operator_gate = get_micro_live_operator_approval_gate_payload(
        state_provider,
        event_bus,
    )
    broker_confirmation = get_micro_live_broker_readiness_confirmation_payload(
        state_provider,
        event_bus,
    )
    return build_micro_live_pre_pilot_go_no_go_payload(
        pilot_readiness=pilot_readiness,
        order_intent=order_intent,
        dry_run_probe=dry_run_probe,
        operator_approval_gate=operator_gate,
        broker_readiness_confirmation=broker_confirmation,
        pcnrass_summary=pcnrass_summary,
    )


def create_dashboard_state_router(
    state_provider: DashboardStateProvider | None = None,
    *,
    runtime_event_bus: RuntimeEventBus | None = None,
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

    @router.get("/api/v1/runtime-events")
    def read_runtime_events(
        event_type: str = "",
        subsystem: str = "",
        severity: str = "",
        correlation_id: str = "",
        limit: int = 100,
        export: bool = False,
    ) -> dict[str, Any]:
        return get_runtime_events_payload(
            runtime_event_bus,
            event_type=event_type,
            subsystem=subsystem,
            severity=severity,
            correlation_id=correlation_id,
            limit=limit,
            export=export,
        )

    @router.get("/api/v1/runtime-event-persistence-policy")
    def read_runtime_event_persistence_policy() -> dict[str, Any]:
        return get_runtime_event_persistence_policy_inspection_payload()

    @router.get("/api/v1/runtime-event-persistence-sim")
    def read_runtime_event_persistence_sim(
        event_type: str = "",
        subsystem: str = "",
        severity: str = "",
        correlation_id: str = "",
        limit: int = 100,
        requested_window_minutes: int = 15,
        reason: str = "runtime event persistence dry-run simulation",
        operator_id: str = "",
        approval_token_present: bool = False,
        requested_export_format: str = "json",
    ) -> dict[str, Any]:
        return get_runtime_event_persistence_sim_payload(
            runtime_event_bus,
            event_type=event_type,
            subsystem=subsystem,
            severity=severity,
            correlation_id=correlation_id,
            limit=limit,
            requested_window_minutes=requested_window_minutes,
            reason=reason,
            operator_id=operator_id,
            approval_token_present=approval_token_present,
            requested_export_format=requested_export_format,
        )

    @router.get("/api/v1/runtime-event-persistence-scenarios")
    def read_runtime_event_persistence_scenarios(
        event_type: str = "",
        subsystem: str = "",
        severity: str = "",
        correlation_id: str = "",
        limit: int = 100,
        requested_window_minutes: int = 15,
        reason: str = "runtime event persistence dry-run scenario",
        operator_id: str = "",
        approval_token_present: bool = False,
        requested_export_format: str = "json",
    ) -> dict[str, Any]:
        return get_runtime_event_persistence_scenarios_payload(
            runtime_event_bus,
            event_type=event_type,
            subsystem=subsystem,
            severity=severity,
            correlation_id=correlation_id,
            limit=limit,
            requested_window_minutes=requested_window_minutes,
            reason=reason,
            operator_id=operator_id,
            approval_token_present=approval_token_present,
            requested_export_format=requested_export_format,
        )

    @router.get("/api/v1/runtime-event-persistence-report")
    def read_runtime_event_persistence_report(
        event_type: str = "",
        subsystem: str = "",
        severity: str = "",
        correlation_id: str = "",
        limit: int = 100,
        requested_window_minutes: int = 15,
        reason: str = "runtime event persistence dry-run report",
        operator_id: str = "",
        approval_token_present: bool = False,
        requested_export_format: str = "json",
    ) -> dict[str, Any]:
        return get_runtime_event_persistence_report_payload(
            runtime_event_bus,
            event_type=event_type,
            subsystem=subsystem,
            severity=severity,
            correlation_id=correlation_id,
            limit=limit,
            requested_window_minutes=requested_window_minutes,
            reason=reason,
            operator_id=operator_id,
            approval_token_present=approval_token_present,
            requested_export_format=requested_export_format,
        )

    @router.get("/api/v1/runtime-event-persistence-checklist")
    def read_runtime_event_persistence_checklist(
        event_type: str = "",
        subsystem: str = "",
        severity: str = "",
        correlation_id: str = "",
        limit: int = 100,
        requested_window_minutes: int = 15,
        reason: str = "runtime event persistence operator checklist",
        operator_id: str = "",
        approval_token_present: bool = False,
        requested_export_format: str = "json",
    ) -> dict[str, Any]:
        return get_runtime_event_persistence_checklist_payload(
            runtime_event_bus,
            event_type=event_type,
            subsystem=subsystem,
            severity=severity,
            correlation_id=correlation_id,
            limit=limit,
            requested_window_minutes=requested_window_minutes,
            reason=reason,
            operator_id=operator_id,
            approval_token_present=approval_token_present,
            requested_export_format=requested_export_format,
        )

    @router.get("/api/v1/runtime-event-persistence-checklist-export")
    def read_runtime_event_persistence_checklist_export(
        event_type: str = "",
        subsystem: str = "",
        severity: str = "",
        correlation_id: str = "",
        limit: int = 100,
        requested_window_minutes: int = 15,
        reason: str = "runtime event persistence checklist export",
        operator_id: str = "",
        approval_token_present: bool = False,
        requested_export_format: str = "json",
    ) -> dict[str, Any]:
        return get_runtime_event_persistence_checklist_export_payload(
            runtime_event_bus,
            event_type=event_type,
            subsystem=subsystem,
            severity=severity,
            correlation_id=correlation_id,
            limit=limit,
            requested_window_minutes=requested_window_minutes,
            reason=reason,
            operator_id=operator_id,
            approval_token_present=approval_token_present,
            requested_export_format=requested_export_format,
        )

    @router.get("/api/v1/micro-live-pilot-readiness")
    def read_micro_live_pilot_readiness() -> dict[str, Any]:
        return get_micro_live_pilot_readiness_payload(
            state_provider,
            runtime_event_bus,
        )

    @router.get("/api/v1/micro-live-pilot-order-intent")
    def read_micro_live_pilot_order_intent() -> dict[str, Any]:
        return get_micro_live_pilot_order_intent_payload()

    @router.get("/api/v1/coinbase-micro-live-dry-run-probe")
    def read_coinbase_micro_live_dry_run_probe() -> dict[str, Any]:
        return get_coinbase_micro_live_dry_run_probe_payload()

    @router.get("/api/v1/micro-live-operator-approval-gate")
    def read_micro_live_operator_approval_gate() -> dict[str, Any]:
        return get_micro_live_operator_approval_gate_payload(
            state_provider,
            runtime_event_bus,
        )

    @router.get("/api/v1/micro-live-broker-readiness-confirmation")
    def read_micro_live_broker_readiness_confirmation() -> dict[str, Any]:
        return get_micro_live_broker_readiness_confirmation_payload(
            state_provider,
            runtime_event_bus,
        )

    @router.get("/api/v1/micro-live-pre-pilot-go-no-go")
    def read_micro_live_pre_pilot_go_no_go() -> dict[str, Any]:
        return get_micro_live_pre_pilot_go_no_go_payload(
            state_provider,
            runtime_event_bus,
        )

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
    *,
    runtime_event_bus: RuntimeEventBus | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Capital Strata Systems Dashboard Runtime API",
        version="0.1.0",
    )
    app.include_router(
        create_dashboard_state_router(
            state_provider,
            runtime_event_bus=runtime_event_bus,
        )
    )
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
    "get_coinbase_micro_live_dry_run_probe_payload",
    "get_broker_reconciliation_payload",
    "get_alert_payload",
    "get_dashboard_state_payload",
    "get_frontend_payload",
    "get_live_credential_attestation_payload",
    "get_micro_live_broker_readiness_confirmation_payload",
    "get_micro_live_operator_approval_gate_payload",
    "get_micro_live_pilot_readiness_payload",
    "get_micro_live_pilot_order_intent_payload",
    "get_micro_live_pre_pilot_go_no_go_payload",
    "get_runtime_event_persistence_checklist_export_payload",
    "get_runtime_event_persistence_checklist_payload",
    "get_runtime_event_persistence_policy_inspection_payload",
    "get_runtime_event_persistence_report_payload",
    "get_runtime_event_persistence_scenarios_payload",
    "get_runtime_event_persistence_sim_payload",
    "get_runtime_events_payload",
    "get_trade_lifecycle_replay_payload",
]
