from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


CERTIFICATION_AREAS = (
    "architecture",
    "runtime",
    "broker",
    "portfolio",
    "decision_intelligence",
    "operations",
    "committees",
    "governance",
    "security",
    "rbac",
    "source_registry",
    "state_hash",
    "runtime_hash",
    "api_contracts",
    "performance",
    "documentation",
    "fail_closed",
    "safety",
)


def build_final_certification(state: Mapping[str, Any]) -> dict[str, Any]:
    checks = [_check(state, area) for area in CERTIFICATION_AREAS]
    blockers = [check["area"] for check in checks if check["status"] != "CERTIFIED"]
    overall = "CERTIFIED" if not blockers else "FAIL_CLOSED"
    return {
        "version": "Mission Control v1.0",
        "overall": overall,
        "checks": checks,
        "blockers": blockers,
        "api_contracts": _api_contracts(state),
        "performance": _performance(state),
        "resilience": _resilience(state),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "final_certification"),
    }


def _check(state: Mapping[str, Any], area: str) -> dict[str, Any]:
    status = "CERTIFIED"
    reason = "evidence_present"
    if area == "architecture":
        reason = "canonical_mission_control_state_contract"
    elif area == "runtime":
        runtime = _mapping(state.get("runtime"))
        if _runtime_unavailable(state):
            status, reason = "FAIL_CLOSED", "runtime_unavailable"
        else:
            reason = str(runtime.get("runtime_status", "runtime_available"))
    elif area == "broker":
        active = _mapping(_mapping(state.get("brokers")).get("active_broker"))
        if active.get("selected_broker") in {DATA_UNAVAILABLE, "UNAVAILABLE", None, ""}:
            status, reason = "FAIL_CLOSED", "broker_unavailable"
        else:
            reason = str(active.get("connection_status", "broker_evidence_present"))
    elif area == "portfolio":
        portfolio = _mapping(state.get("portfolio"))
        if portfolio.get("equity") == DATA_UNAVAILABLE:
            status, reason = "FAIL_CLOSED", "portfolio_unavailable"
    elif area == "decision_intelligence":
        if _mapping(state.get("decision_panel")).get("status") in {"UNKNOWN", DATA_UNAVAILABLE}:
            status, reason = "FAIL_CLOSED", "decision_evidence_unavailable"
    elif area == "operations":
        if not _mapping(state.get("operations_timeline")).get("events"):
            status, reason = "FAIL_CLOSED", "operations_timeline_unavailable"
    elif area == "committees":
        if _mapping(state.get("committee_view")).get("status") == "FAIL_CLOSED":
            status, reason = "FAIL_CLOSED", "committee_evidence_failed"
    elif area == "governance":
        if _mapping(state.get("governance_summary_console")).get("status") == "fail_closed":
            status, reason = "FAIL_CLOSED", "governance_summary_failed"
    elif area == "security":
        safety = _mapping(state.get("safety"))
        if safety.get("safety_status") != "PASS":
            status, reason = "FAIL_CLOSED", "safety_status_not_pass"
    elif area == "rbac":
        if _mapping(state.get("rbac_console")).get("status") == "fail_closed":
            status, reason = "FAIL_CLOSED", "rbac_console_failed"
    elif area == "source_registry":
        if _mapping(state.get("source_consistency")).get("status") == "FAIL_CLOSED":
            status, reason = "FAIL_CLOSED", "source_consistency_failed"
    elif area == "state_hash":
        if state.get("state_hash") in {None, "", DATA_UNAVAILABLE}:
            status, reason = "FAIL_CLOSED", "state_hash_missing"
    elif area == "runtime_hash":
        if _mapping(state.get("runtime")).get("state_hash") in {None, "", DATA_UNAVAILABLE}:
            status, reason = "FAIL_CLOSED", "runtime_hash_missing"
    elif area == "api_contracts":
        reason = "get_only_routes_and_shared_state_cache"
    elif area == "performance":
        reason = "single_state_generation_per_route_cache_window"
    elif area == "documentation":
        docs = _mapping(state.get("documentation"))
        governance = docs.get("governance") if isinstance(docs.get("governance"), list) else []
        if "docs/governance/MISSION_CONTROL_FINAL_CERTIFICATION.md" not in governance:
            status, reason = "FAIL_CLOSED", "final_certification_doc_missing"
    elif area == "fail_closed":
        validation = _mapping(state.get("contract_validation"))
        if validation and validation.get("valid") is not True:
            status, reason = "FAIL_CLOSED", "contract_validation_failed"
    elif area == "safety":
        safety = _mapping(state.get("safety"))
        expected = {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }
        if any(safety.get(key) is not value for key, value in expected.items()):
            status, reason = "FAIL_CLOSED", "safety_flag_invalid"
    return {"area": area, "status": status, "reason": reason}


def _api_contracts(state: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    freshness = _mapping(state.get("freshness"))
    return {
        "schema_version": state.get("schema_version", DATA_UNAVAILABLE),
        "state_hash": state.get("state_hash", DATA_UNAVAILABLE),
        "runtime_id": runtime.get("runtime_id", DATA_UNAVAILABLE),
        "runtime_state_hash": runtime.get("state_hash", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "get_only": True,
        "shared_state_contract": True,
    }


def _performance(state: Mapping[str, Any]) -> dict[str, Any]:
    system = _mapping(state.get("system_metrics"))
    return {
        "refresh_interval_seconds": system.get("refresh_interval_seconds", 5),
        "state_generation": "single_contract_builder",
        "route_cache_seconds": 5,
        "projection_side_effects": "none",
    }


def _resilience(state: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    health = _mapping(state.get("health"))
    return {
        "runtime_status": runtime.get("runtime_status", DATA_UNAVAILABLE),
        "heartbeat_status": runtime.get("heartbeat_status", DATA_UNAVAILABLE),
        "health": health.get("health", DATA_UNAVAILABLE),
        "fail_closed": _mapping(state.get("safety")).get("fail_closed", False),
    }


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["CERTIFICATION_AREAS", "build_final_certification"]
