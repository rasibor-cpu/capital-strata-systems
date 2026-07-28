from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider
from dashboard.mission_control.runtime_source_resolver import RuntimeSourceResolver
from dashboard.runtime.frontend_contract import build_frontend_payload


PAYLOAD_VERSION = "css.phase170.operational_compatibility_validator.v1"
UNAVAILABLE_VALUES = {"", "UNAVAILABLE", "DATA UNAVAILABLE", "N/A", "NONE", "UNKNOWN"}

RuntimeSource = Callable[[], Mapping[str, Any] | None]


def validate_operational_compatibility(
    source: RuntimeSource | None = None,
    *,
    artifact_root: str | Path = "artifacts",
    supervisor_state_path: str | Path = "runtime/supervisor/css_runtime_supervisor_state.json",
    endpoint_url: str | None = None,
    allow_mock: bool = False,
) -> dict[str, Any]:
    """Validate runtime/frontend/Mission Control compatibility using active read-only sources."""

    resolver = RuntimeSourceResolver(
        source,
        artifact_root=artifact_root,
        supervisor_state_path=supervisor_state_path,
        endpoint_url=endpoint_url,
    )
    resolved = resolver.resolve()
    provider = RuntimeSnapshotProvider(
        source,
        artifact_root=artifact_root,
        supervisor_state_path=supervisor_state_path,
        endpoint_url=endpoint_url,
        active_source_binding=True,
    )
    state_payload = provider.get_state_payload()

    runtime_snapshot = state_payload.get("runtime_snapshot") if isinstance(state_payload.get("runtime_snapshot"), Mapping) else {}
    runtime_snapshot = dict(runtime_snapshot)

    frontend_payload = _frontend_payload(state_payload=state_payload, resolved=resolved, source=source)
    mission_control_state = build_mission_control_state(state_payload, allow_mock=allow_mock)

    return evaluate_operational_compatibility_views(
        runtime_snapshot=runtime_snapshot,
        frontend_payload=frontend_payload,
        mission_control_state=mission_control_state,
        source_diagnostics=state_payload.get("runtime_source_diagnostics") if isinstance(state_payload.get("runtime_source_diagnostics"), Mapping) else resolved.get("diagnostics"),
    )


def evaluate_operational_compatibility_views(
    *,
    runtime_snapshot: Mapping[str, Any],
    frontend_payload: Mapping[str, Any],
    mission_control_state: Mapping[str, Any],
    source_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate compatibility checks for already materialized runtime/frontend/mission views."""

    checks = [
        _check_safety_flags(runtime_snapshot, frontend_payload, mission_control_state),
        _check_source_alignment(runtime_snapshot, source_diagnostics),
        _check_state_hash_alignment(runtime_snapshot, mission_control_state),
        _check_broker_alignment(runtime_snapshot, frontend_payload, mission_control_state),
        _check_portfolio_alignment(runtime_snapshot, mission_control_state),
        _check_risk_alignment(runtime_snapshot, mission_control_state),
        _check_certification_alignment(runtime_snapshot, mission_control_state),
        _check_unavailable_projection(runtime_snapshot, mission_control_state),
    ]

    fail_count = sum(1 for item in checks if item["status"] == "FAIL")
    warn_count = sum(1 for item in checks if item["status"] == "WARN")
    pass_count = sum(1 for item in checks if item["status"] == "PASS")

    status = "PASS"
    if fail_count:
        status = "FAIL_CLOSED"
    elif warn_count:
        status = "PASS_WITH_WARNINGS"

    return {
        "payload_version": PAYLOAD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": {
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
        },
        "runtime_source": str(runtime_snapshot.get("source", "UNAVAILABLE")),
        "runtime_status": str(runtime_snapshot.get("runtime_status", "UNAVAILABLE")),
        "checks": checks,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _frontend_payload(
    *,
    state_payload: Mapping[str, Any],
    resolved: Mapping[str, Any],
    source: RuntimeSource | None,
) -> dict[str, Any]:
    embedded = state_payload.get("frontend_payload")
    if isinstance(embedded, Mapping) and isinstance(embedded.get("sections"), Mapping):
        return dict(embedded)

    payload = resolved.get("payload") if isinstance(resolved.get("payload"), Mapping) else {}
    from_resolved = payload.get("frontend_payload") if isinstance(payload.get("frontend_payload"), Mapping) else {}
    if isinstance(from_resolved.get("sections"), Mapping):
        return dict(from_resolved)

    source_payload = source() if source is not None else {}
    if isinstance(source_payload, Mapping) and isinstance(source_payload.get("sections"), Mapping):
        return dict(source_payload)
    return build_frontend_payload(source_payload if isinstance(source_payload, Mapping) else {})


def _check_safety_flags(runtime_snapshot: Mapping[str, Any], frontend_payload: Mapping[str, Any], mission_control_state: Mapping[str, Any]) -> dict[str, Any]:
    broker = _section(frontend_payload, "broker")
    safety = mission_control_state.get("safety") if isinstance(mission_control_state.get("safety"), Mapping) else {}

    paths = {
        "runtime_snapshot": runtime_snapshot,
        "frontend.sections.broker": broker,
        "mission_control.safety": safety,
    }
    failures: list[str] = []
    for name, payload in paths.items():
        if payload.get("execution_allowed") is not False:
            failures.append(f"{name}.execution_allowed")
        if payload.get("live_trading_blocked") is not True:
            failures.append(f"{name}.live_trading_blocked")
        if payload.get("broker_execution_armed") is not False:
            failures.append(f"{name}.broker_execution_armed")

    if failures:
        return _check("safety_flags", "FAIL", "Read-only safety flags violated.", failures=failures)
    return _check("safety_flags", "PASS", "Read-only safety flags are preserved across views.")


def _check_source_alignment(runtime_snapshot: Mapping[str, Any], source_diagnostics: Mapping[str, Any] | None) -> dict[str, Any]:
    runtime_source = str(runtime_snapshot.get("source", "UNAVAILABLE")).upper()
    selected = "UNAVAILABLE"
    if isinstance(source_diagnostics, Mapping):
        selected = str(source_diagnostics.get("selected_source", "UNAVAILABLE")).upper()

    if runtime_source == selected:
        return _check("runtime_source_alignment", "PASS", "Runtime snapshot source matches resolver selected source.")
    if runtime_source in UNAVAILABLE_VALUES and selected in UNAVAILABLE_VALUES:
        return _check("runtime_source_alignment", "PASS", "Runtime and resolver both report unavailable source.")
    return _check(
        "runtime_source_alignment",
        "WARN",
        "Runtime snapshot source differs from resolver diagnostics.",
        expected=selected,
        observed=runtime_source,
    )


def _check_state_hash_alignment(runtime_snapshot: Mapping[str, Any], mission_control_state: Mapping[str, Any]) -> dict[str, Any]:
    runtime_hash = str(runtime_snapshot.get("state_hash", "UNAVAILABLE"))
    mission_snapshot = mission_control_state.get("runtime_snapshot") if isinstance(mission_control_state.get("runtime_snapshot"), Mapping) else {}
    runtime_section = mission_control_state.get("runtime") if isinstance(mission_control_state.get("runtime"), Mapping) else {}
    mission_hash = str(mission_snapshot.get("state_hash") or runtime_section.get("state_hash", "UNAVAILABLE"))

    if runtime_hash == mission_hash and runtime_hash not in UNAVAILABLE_VALUES:
        return _check("state_hash_alignment", "PASS", "Mission Control runtime hash matches runtime snapshot hash.")
    if runtime_hash in UNAVAILABLE_VALUES and mission_hash in UNAVAILABLE_VALUES:
        return _check("state_hash_alignment", "WARN", "State hash is unavailable in runtime and Mission Control.")
    if _runtime_identity_matches(runtime_snapshot, mission_snapshot):
        return _check(
            "state_hash_alignment",
            "PASS",
            "Runtime identity and source match; independently regenerated volatile hashes are tracked but not treated as authority divergence.",
            expected=runtime_hash,
            observed=mission_hash,
        )
    return _check(
        "state_hash_alignment",
        "FAIL",
        "Mission Control runtime hash diverges from runtime snapshot hash.",
        expected=runtime_hash,
        observed=mission_hash,
    )


def _check_broker_alignment(runtime_snapshot: Mapping[str, Any], frontend_payload: Mapping[str, Any], mission_control_state: Mapping[str, Any]) -> dict[str, Any]:
    runtime_broker = runtime_snapshot.get("broker") if isinstance(runtime_snapshot.get("broker"), Mapping) else {}
    frontend_broker = _section(frontend_payload, "broker")
    brokers = mission_control_state.get("brokers") if isinstance(mission_control_state.get("brokers"), Mapping) else {}
    active_broker = brokers.get("active_broker") if isinstance(brokers.get("active_broker"), Mapping) else {}
    platform = mission_control_state.get("platform") if isinstance(mission_control_state.get("platform"), Mapping) else {}

    values = {
        "runtime": str(runtime_broker.get("selected_broker", "UNAVAILABLE")).upper(),
        "frontend": str(frontend_broker.get("selected_broker", "UNAVAILABLE")).upper(),
        "mission.active_broker": str(active_broker.get("selected_broker", "UNAVAILABLE")).upper(),
        "mission.platform": str(platform.get("selected_broker", "UNAVAILABLE")).upper(),
    }
    normalized = {value for value in values.values() if value not in UNAVAILABLE_VALUES}
    if len(normalized) <= 1:
        return _check("broker_consistency", "PASS", "Broker selection is consistent across runtime/frontend/Mission Control.", observed=values)

    return _check("broker_consistency", "FAIL", "Broker selection mismatch across views.", observed=values)


def _check_portfolio_alignment(runtime_snapshot: Mapping[str, Any], mission_control_state: Mapping[str, Any]) -> dict[str, Any]:
    if _runtime_unavailable(runtime_snapshot):
        return _check("portfolio_consistency", "PASS", "Runtime unavailable; portfolio consistency check deferred to unavailable projection.")

    runtime_portfolio = runtime_snapshot.get("portfolio") if isinstance(runtime_snapshot.get("portfolio"), Mapping) else {}
    mission_portfolio = mission_control_state.get("portfolio") if isinstance(mission_control_state.get("portfolio"), Mapping) else {}

    keys = ("equity", "cash", "buying_power", "net_pnl")
    mismatches = []
    for key in keys:
        expected = _normalized_value(runtime_portfolio.get(key))
        observed = _normalized_value(mission_portfolio.get(key))
        if expected != observed:
            mismatches.append({"field": key, "expected": expected, "observed": observed})

    if mismatches:
        return _check("portfolio_consistency", "FAIL", "Portfolio values diverge between runtime snapshot and Mission Control.", mismatches=mismatches)
    return _check("portfolio_consistency", "PASS", "Portfolio values are consistent with runtime snapshot.")


def _check_risk_alignment(runtime_snapshot: Mapping[str, Any], mission_control_state: Mapping[str, Any]) -> dict[str, Any]:
    if _runtime_unavailable(runtime_snapshot):
        return _check("risk_consistency", "PASS", "Runtime unavailable; risk consistency check deferred to unavailable projection.")

    runtime_risk = runtime_snapshot.get("risk") if isinstance(runtime_snapshot.get("risk"), Mapping) else {}
    mission_risk = mission_control_state.get("risk") if isinstance(mission_control_state.get("risk"), Mapping) else {}

    expected = str(runtime_risk.get("risk_status", "UNAVAILABLE")).upper()
    observed = str(mission_risk.get("overall_risk_state", "UNAVAILABLE")).upper()
    if expected == observed:
        return _check("risk_consistency", "PASS", "Risk state is consistent with runtime snapshot.")
    return _check("risk_consistency", "FAIL", "Risk state mismatch between runtime snapshot and Mission Control.", expected=expected, observed=observed)


def _check_certification_alignment(runtime_snapshot: Mapping[str, Any], mission_control_state: Mapping[str, Any]) -> dict[str, Any]:
    runtime_cert = runtime_snapshot.get("certification") if isinstance(runtime_snapshot.get("certification"), Mapping) else {}
    mission_cert = mission_control_state.get("certification") if isinstance(mission_control_state.get("certification"), Mapping) else {}

    expected = str(runtime_cert.get("runtime_readiness", "UNAVAILABLE")).upper()
    observed = str(mission_cert.get("runtime_readiness", "UNAVAILABLE")).upper()
    if expected == observed:
        return _check("certification_consistency", "PASS", "Certification runtime readiness is consistent.")
    return _check("certification_consistency", "WARN", "Certification readiness differs across runtime and Mission Control.", expected=expected, observed=observed)


def _check_unavailable_projection(runtime_snapshot: Mapping[str, Any], mission_control_state: Mapping[str, Any]) -> dict[str, Any]:
    if not _runtime_unavailable(runtime_snapshot):
        return _check("unavailable_projection", "PASS", "Runtime is available; unavailable projection constraints not active.")

    platform = mission_control_state.get("platform") if isinstance(mission_control_state.get("platform"), Mapping) else {}
    portfolio = mission_control_state.get("portfolio") if isinstance(mission_control_state.get("portfolio"), Mapping) else {}
    risk = mission_control_state.get("risk") if isinstance(mission_control_state.get("risk"), Mapping) else {}

    failures: list[str] = []
    if str(platform.get("selected_broker", "UNAVAILABLE")).upper() not in UNAVAILABLE_VALUES:
        failures.append("platform.selected_broker")
    for field in ("equity", "cash", "buying_power"):
        if str(portfolio.get(field, "UNAVAILABLE")).upper() not in UNAVAILABLE_VALUES:
            failures.append(f"portfolio.{field}")
    if str(risk.get("overall_risk_state", "UNAVAILABLE")).upper() not in UNAVAILABLE_VALUES:
        failures.append("risk.overall_risk_state")

    if failures:
        return _check("unavailable_projection", "FAIL", "UNAVAILABLE runtime projection is not preserved in Mission Control views.", failures=failures)
    return _check("unavailable_projection", "PASS", "UNAVAILABLE runtime projection is correctly preserved.")


def _runtime_identity_matches(runtime_snapshot: Mapping[str, Any], mission_snapshot: Mapping[str, Any]) -> bool:
    if not mission_snapshot:
        return False
    for key in ("runtime_id", "session_id", "source"):
        left = str(runtime_snapshot.get(key, "UNAVAILABLE")).upper()
        right = str(mission_snapshot.get(key, "UNAVAILABLE")).upper()
        if left in UNAVAILABLE_VALUES or right in UNAVAILABLE_VALUES or left != right:
            return False
    return True


def _runtime_unavailable(runtime_snapshot: Mapping[str, Any]) -> bool:
    source = str(runtime_snapshot.get("source", "UNAVAILABLE")).upper()
    status = str(runtime_snapshot.get("runtime_status", "UNAVAILABLE")).upper()
    return source in UNAVAILABLE_VALUES or status in {"OFFLINE", "UNAVAILABLE", "DATA UNAVAILABLE"}


def _section(payload: Mapping[str, Any], section_name: str) -> Mapping[str, Any]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), Mapping) else {}
    value = sections.get(section_name)
    return value if isinstance(value, Mapping) else {}


def _normalized_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, int):
        return float(value)
    text = str(value).strip().upper()
    if text in UNAVAILABLE_VALUES:
        return "UNAVAILABLE"
    return value


def _check(name: str, status: str, message: str, **details: Any) -> dict[str, Any]:
    payload = {
        "name": name,
        "status": status,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


__all__ = [
    "PAYLOAD_VERSION",
    "evaluate_operational_compatibility_views",
    "validate_operational_compatibility",
]
