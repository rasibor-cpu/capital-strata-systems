from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.brokers.canonical_tier1 import get_canonical_broker_registry
from backend.app.brokers.contamination_isolation import (
    analyze_environment_contamination,
    analyze_runtime_state_contamination,
    merge_contamination_reports,
)
from backend.runtime.canonical_broker_state_adapter import broker_environment_profile_view
from dashboard.mission_control.mock_data import mission_control_mock_dashboard_payload
from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE, build_frontend_payload


def frontend_payload_from_runtime(
    dashboard_state: Any = None,
    *,
    allow_mock: bool = True,
) -> dict[str, Any]:
    if isinstance(dashboard_state, Mapping) and isinstance(dashboard_state.get("frontend_payload"), Mapping):
        payload = dict(dashboard_state["frontend_payload"])
        payload["mission_control_data_source"] = str(dashboard_state.get("source") or payload.get("mission_control_data_source") or "RUNTIME").upper()
        payload["mission_control_mock_data"] = _is_mock_source(dashboard_state)
        payload["mission_control_dashboard_state_available"] = True
        return payload
    if isinstance(dashboard_state, Mapping) and dashboard_state.get("payload_schema") == "css.frontend.contract.v1" and isinstance(dashboard_state.get("sections"), Mapping):
        payload = dict(dashboard_state)
        payload["mission_control_data_source"] = str(payload.get("mission_control_data_source") or "RUNTIME").upper()
        payload["mission_control_mock_data"] = _is_mock_source(dashboard_state)
        payload["mission_control_dashboard_state_available"] = True
        return payload

    source = dashboard_state if dashboard_state is not None else None
    if source is None and allow_mock:
        source = mission_control_mock_dashboard_payload()
    payload = build_frontend_payload(source or {})
    if _is_mock_source(source):
        data_source = "MOCK"
    elif source is None:
        data_source = "UNAVAILABLE"
    else:
        data_source = "RUNTIME"
    payload["mission_control_data_source"] = data_source
    payload["mission_control_mock_data"] = _is_mock_source(source)
    payload["mission_control_dashboard_state_available"] = source is not None
    return payload


def _is_mock_source(source: Any) -> bool:
    if isinstance(source, Mapping):
        return bool(source.get("mock_data") or source.get("mission_control_mock_data") or source.get("source") == "DEMO")
    return False


def section(payload: Mapping[str, Any], name: str) -> dict[str, Any]:
    sections = payload.get("sections")
    if isinstance(sections, Mapping):
        value = sections.get(name)
        if isinstance(value, Mapping):
            return dict(value)
    return {"status": DATA_UNAVAILABLE}


def _broker_evidence_overlays(active_broker: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return sanitized per-broker read-only evidence for Mission Control display.

    Tier-1 registry rows are static capability records. This overlay lets
    Mission Control distinguish "never configured" from evidence that was
    previously captured for Coinbase/OANDA or a Questrade secure token store
    that needs reactivation after process restart. It never enables execution.
    """

    overlays: dict[str, dict[str, Any]] = {}

    for broker, key in (
        ("COINBASE", "coinbase_live_validation"),
        ("OANDA", "oanda_live_validation"),
    ):
        payload = active_broker.get(key)
        if not isinstance(payload, Mapping):
            continue
        validation = str(payload.get("validation_status") or "").strip().upper()
        timestamp = str(payload.get("validation_timestamp") or "").strip()
        last_sync = str(payload.get("last_successful_sync") or "").strip()
        operational = payload.get("broker_operational_status")
        operational = dict(operational) if isinstance(operational, Mapping) else {}
        state = str(
            operational.get("operational_state")
            or payload.get("operational_state")
            or ""
        ).strip().upper()
        has_evidence = (
            validation not in {"", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_AVAILABLE"}
            or timestamp not in {"", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_AVAILABLE"}
            or last_sync not in {"", "DATA UNAVAILABLE", "UNAVAILABLE", "NOT_AVAILABLE"}
        )
        if not has_evidence:
            continue
        if validation == "PASS":
            readiness = "READ_ONLY_READY"
            certification = "READ_ONLY_VALIDATED"
            state = state or "READ_ONLY_READY"
        else:
            readiness = "FAIL_CLOSED" if validation in {"FAIL", "FAIL_CLOSED", "FAILED"} else "EVIDENCE_PRESENT"
            certification = "NOT_CERTIFIED"
            state = state or readiness
        overlays[broker] = {
            "operational_state": state,
            "status": state,
            "readiness": readiness,
            "certification": certification,
            "authentication": "AUTHENTICATED" if bool(payload.get("authentication")) else "UNAVAILABLE",
            "market_data": "OK" if bool(payload.get("market_data_loaded")) else str(payload.get("market_data_status") or "UNAVAILABLE"),
            "account": "AVAILABLE" if bool(payload.get("account_loaded")) else str(payload.get("account_sync_status") or "UNAVAILABLE"),
            "last_sync": last_sync or timestamp or "UNAVAILABLE",
            "evidence_source": "PERSISTED_READ_ONLY_VALIDATION",
            "execution": "DISABLED",
            "execution_authority": "BLOCKED",
            "execution_blocked": True,
            "advisory_only": True,
        }

    questrade = active_broker.get("questrade_read_only_status")
    if isinstance(questrade, Mapping):
        status = str(questrade.get("status") or "").strip().upper()
        secure_store = bool(questrade.get("secure_token_store_present"))
        if status == "READY":
            overlays["QUESTRADE"] = {
                "operational_state": "READ_ONLY_READY",
                "status": "READ_ONLY_READY",
                "readiness": "READ_ONLY_READY",
                "certification": "READ_ONLY_VALIDATED",
                "authentication": "AUTHENTICATED",
                "evidence_source": "IN_PROCESS_READ_ONLY_ACTIVATION",
                "execution": "DISABLED",
                "execution_authority": "BLOCKED",
                "execution_blocked": True,
                "advisory_only": True,
            }
        elif secure_store:
            overlays["QUESTRADE"] = {
                "operational_state": "REACTIVATION_REQUIRED",
                "status": "REACTIVATION_REQUIRED",
                "readiness": "CONFIGURED_REACTIVATION_REQUIRED",
                "certification": "NOT_CERTIFIED",
                "authentication": "REACTIVATION_REQUIRED",
                "evidence_source": "SECURE_TOKEN_STORE_PRESENT",
                "execution": "DISABLED",
                "execution_authority": "BLOCKED",
                "execution_blocked": True,
                "advisory_only": True,
            }

    return overlays


def build_broker_registry(active_broker: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Phase 177C — Mission Control rows from canonical Tier-1 registry (no IBKR)."""
    selected = str(active_broker.get("selected_broker", active_broker.get("broker", "NONE"))).upper()
    profile = _profile_metadata(active_broker)
    env_report = analyze_environment_contamination(selected_broker=selected)
    runtime_report = analyze_runtime_state_contamination(active_broker)
    contamination = merge_contamination_reports(env_report, runtime_report)
    rows = get_canonical_broker_registry().mission_control_rows(
        selected_broker=selected,
        active=active_broker,
        contamination_by_broker=contamination.findings_by_broker(),
    )
    overlays = _broker_evidence_overlays(active_broker)
    for row in rows:
        broker_name = str(row.get("broker") or "").upper()
        overlay = overlays.get(broker_name)
        if overlay:
            row.update(overlay)
        row["profile"] = profile if row.get("selected") else _inactive_profile()
        row["account_data"] = row.get("account")
        row["broker_status"] = row.get("status")
        row["broker_role"] = row.get("role")
    # Paper/NONE selection marker (not a Tier-1 broker; simulation lane)
    if selected in {"PAPER", "DEMO", "NONE", ""}:
        rows.append(
            {
                "broker": "PAPER",
                "role": "SIMULATION_LANE",
                "broker_role": "SIMULATION_LANE",
                "broker_type": "SIMULATION",
                "status": "AVAILABLE",
                "operational_state": "AVAILABLE",
                "mode": "paper",
                "readiness": "READY_FOR_PAPER",
                "certification": "NOT_REQUIRED",
                "latency": "UNAVAILABLE",
                "authentication": "NOT_REQUIRED",
                "market_data": "SIMULATION",
                "account": "SIMULATION",
                "account_data": "SIMULATION",
                "execution": "DISABLED",
                "execution_authority": "BLOCKED",
                "last_sync": "UNAVAILABLE",
                "credentials_present": "NOT_REQUIRED",
                "supported_assets": ["STOCK", "ETF", "OPTION", "FOREX", "CRYPTO"],
                "capabilities": ["simulation", "paper_positions", "paper_orders"],
                "selected": True,
                "priority": 99,
                "execution_blocked": True,
                "advisory_only": True,
                "profile": profile if selected in {"PAPER", "DEMO", "NONE", ""} else _inactive_profile(profile_name="PAPER"),
                "contamination_isolated": True,
                "contamination_findings": [],
            }
        )
    return rows


def _profile_metadata(active_broker: Mapping[str, Any]) -> dict[str, Any]:
    profile = active_broker.get("broker_environment_profile")
    if not isinstance(profile, Mapping):
        canonical = active_broker.get("canonical_broker_runtime_state")
        if isinstance(canonical, Mapping):
            profile = canonical.get("environment_evidence")
    return broker_environment_profile_view(
        profile,
        fallback=active_broker,
        default_environment=str(active_broker.get("broker_mode", "paper")),
    )


def _inactive_profile(*, profile_name: str = "UNSELECTED") -> dict[str, Any]:
    return broker_environment_profile_view(default_profile=profile_name, inactive=True)


__all__ = [
    "build_broker_registry",
    "frontend_payload_from_runtime",
    "section",
]
