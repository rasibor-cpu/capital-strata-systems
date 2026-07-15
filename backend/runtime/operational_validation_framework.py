from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from backend.runtime.broker_readiness_consolidation import build_canonical_broker_readiness
from backend.runtime.canonical_runtime_snapshot import build_canonical_runtime_snapshot, stable_state_hash


SCHEMA_VERSION = "css.op002.operational_validation.v1"


def build_operational_validation_report(
    *,
    runtime_payload: Mapping[str, Any] | None = None,
    mission_control_state: Mapping[str, Any] | None = None,
    frontend_payload: Mapping[str, Any] | None = None,
    certification_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build OP-002 read-only operational validation evidence."""

    frontend = _mapping(frontend_payload)
    source = _mapping(runtime_payload) or frontend
    mission = _mapping(mission_control_state)
    mission_runtime = _mapping(mission.get("runtime_snapshot"))
    runtime_snapshot = (
        mission_runtime
        if mission_runtime
        else build_canonical_runtime_snapshot(source, frontend if frontend else None, source_name="op002_operational_validation")
    )
    sections = _mapping(frontend.get("sections"))
    broker_section = _mapping(sections.get("broker"))
    certification = _mapping(certification_snapshot or sections.get("runtime_certification_snapshot"))
    broker_readiness = build_canonical_broker_readiness(
        broker_section=broker_section,
        runtime_snapshot=runtime_snapshot,
        certification_snapshot=certification,
    )

    safety = _safety_assertions(runtime_snapshot, mission, broker_readiness)
    checks = {
        "desktop_runtime": _check_present(runtime_snapshot.get("runtime_status")),
        "mission_control": _check_present(mission.get("schema_version") or mission_runtime),
        "dashboard": _check_present(frontend.get("payload_schema")),
        "launcher": _check_present(frontend.get("source_metadata") or runtime_snapshot.get("source")),
        "runtime_supervisor": _check_present(runtime_snapshot.get("runtime_status")),
        "runtime_artifacts": _check_present(runtime_snapshot.get("provenance")),
        "heartbeat": _check_status(runtime_snapshot.get("heartbeat_status"), pass_values={"FRESH", "AGING"}),
        "broker_readiness": _check_status(broker_readiness.get("overall_status"), pass_values={"GREEN", "AMBER"}),
        "portfolio": _check_present(_mapping(runtime_snapshot.get("portfolio")).get("equity")),
        "risk": _check_present(_mapping(runtime_snapshot.get("risk")).get("risk_status")),
        "decision_intelligence": _check_present(_mapping(runtime_snapshot.get("decision_intelligence")).get("status")),
        "certification": _check_present(_mapping(runtime_snapshot.get("certification")).get("runtime_readiness")),
        "runtime_hash": _check_present(runtime_snapshot.get("state_hash")),
        "mission_control_hash": _hash_consistency(runtime_snapshot, mission_runtime),
        "options_income": _check_present(_mapping(runtime_snapshot.get("options_income")).get("status")),
        "portfolio_risk_capital": _portfolio_risk_capital(runtime_snapshot),
        "safety": {"status": "PASS" if safety["passed"] else "FAIL", "details": safety},
    }
    blockers = [name for name, check in checks.items() if _mapping(check).get("status") == "FAIL"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_snapshot": runtime_snapshot,
        "broker_readiness": broker_readiness,
        "checks": checks,
        "summary": {
            "status": "PASS" if not blockers else "FAIL_CLOSED",
            "blockers": blockers,
            "validated_surfaces": sorted(checks.keys()),
            "canonical_runtime_owner": "backend.runtime.canonical_runtime_snapshot",
            "canonical_broker_owner": "backend.runtime.broker_readiness_consolidation",
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _safety_assertions(*payloads: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    for index, payload in enumerate(payloads):
        data = _mapping(payload)
        safety = _mapping(data.get("safety"))
        execution_allowed = data.get("execution_allowed", safety.get("execution_allowed"))
        live_trading_blocked = data.get("live_trading_blocked", safety.get("live_trading_blocked"))
        broker_execution_armed = data.get("broker_execution_armed", safety.get("broker_execution_armed"))
        advisory_only = data.get("advisory_only", safety.get("advisory_only"))
        if execution_allowed is not False:
            failures.append(f"payload_{index}:execution_allowed")
        if live_trading_blocked is not True:
            failures.append(f"payload_{index}:live_trading_blocked")
        if broker_execution_armed is not False:
            failures.append(f"payload_{index}:broker_execution_armed")
        if advisory_only is not True:
            failures.append(f"payload_{index}:advisory_only")
    return {
        "passed": not failures,
        "failures": failures,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _check_present(value: Any) -> dict[str, Any]:
    ok = value not in (None, "", "UNAVAILABLE", "DATA UNAVAILABLE")
    return {"status": "PASS" if ok else "FAIL", "value": value}


def _check_status(value: Any, *, pass_values: set[str]) -> dict[str, Any]:
    status = str(value or "").upper()
    return {"status": "PASS" if status in pass_values else "FAIL", "value": value}


def _hash_consistency(runtime_snapshot: Mapping[str, Any], mission_runtime: Mapping[str, Any]) -> dict[str, Any]:
    runtime_hash = runtime_snapshot.get("state_hash")
    mission_hash = mission_runtime.get("state_hash")
    if not mission_runtime:
        return {"status": "PASS", "reason": "mission_control_runtime_snapshot_not_supplied"}
    recomputed = stable_state_hash({key: value for key, value in mission_runtime.items() if key != "state_hash"})
    return {
        "status": "PASS" if runtime_hash and mission_hash and mission_hash == recomputed else "FAIL",
        "runtime_state_hash": runtime_hash,
        "mission_control_state_hash": mission_hash,
        "recomputed_mission_control_state_hash": recomputed,
    }


def _portfolio_risk_capital(runtime_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    portfolio = _mapping(runtime_snapshot.get("portfolio"))
    risk = _mapping(runtime_snapshot.get("risk"))
    missing = [
        name
        for name, value in {
            "equity": portfolio.get("equity"),
            "cash": portfolio.get("cash"),
            "buying_power": portfolio.get("buying_power"),
            "exposure": portfolio.get("exposure"),
            "drawdown": portfolio.get("drawdown", risk.get("drawdown")),
            "risk_status": risk.get("risk_status"),
        }.items()
        if value in (None, "", "UNAVAILABLE", "DATA UNAVAILABLE")
    ]
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["SCHEMA_VERSION", "build_operational_validation_report"]
