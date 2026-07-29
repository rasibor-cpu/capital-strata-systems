"""Read-only operational identity projection for dashboard display."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

OPERATIONAL_IDENTITY_VERSION = "css.operational_identity.v2"

_LIVE_RUNTIME_MODES = frozenset({"LIVE", "LIVE_MICRO_PILOT"})
_ORDER_ALLOWED_STATES = frozenset({"ALLOWED", "ENABLED", "OPEN"})
_READY_STATES = frozenset(
    {
        "CERTIFIED",
        "GREEN",
        "LIVE_READY",
        "OPERATIONAL",
        "PASS",
        "PASSED",
        "READY",
    }
)


def build_operational_identity_payload(
    dashboard_payload: Mapping[str, Any] | None = None,
    *,
    mobile_controls: Mapping[str, Any] | None = None,
    platform_status: Mapping[str, Any] | None = None,
    runtime_resolution: Mapping[str, Any] | None = None,
    broker_readiness: Mapping[str, Any] | None = None,
    certification: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a display payload from already-resolved canonical authority data."""

    payload = _mapping(dashboard_payload)
    platform = _mapping(platform_status) or _mapping(
        payload.get("platform_status") or payload.get("platform")
    )
    runtime = _mapping(runtime_resolution) or _mapping(
        payload.get("runtime_mode_resolution") or platform.get("runtime_mode_resolution")
    )
    broker_summary = _mapping(payload.get("broker_summary"))
    broker = (
        _mapping(broker_readiness)
        or _mapping(payload.get("broker_readiness"))
        or broker_summary
    )
    cert = (
        _mapping(certification)
        or _mapping(payload.get("certification"))
        or _mapping(payload.get("runtime_certification_snapshot"))
        or _mapping(payload.get("live_readiness_certification"))
    )
    governance = _mapping(payload.get("governance_state"))
    session = _mapping(payload.get("session"))

    runtime_mode = _runtime_mode(platform, runtime)
    execution_state = _upper_text(platform.get("execution_state"), "BLOCKED")
    execution_authority = _strict_true(
        platform.get("execution_authority", runtime.get("execution_authority"))
    )
    order_submission = _upper_text(
        platform.get("order_submission", runtime.get("order_submission")),
        "BLOCKED",
    )
    live_trading_enabled = _strict_true(
        platform.get("live_trading_enabled", runtime.get("live_trading_enabled"))
    )
    broker_execution_armed = _strict_true(
        broker.get("broker_execution_armed", cert.get("broker_execution_armed"))
    )
    broker_readiness_status = _upper_text(
        broker.get("readiness_status", cert.get("readiness_status")),
        "UNKNOWN",
    )
    certification_status = _upper_text(
        cert.get("certification_status", cert.get("status", cert.get("overall_state"))),
        "UNKNOWN",
    )
    readiness_ready = broker_readiness_status in _READY_STATES
    certification_ready = certification_status in _READY_STATES
    blockers = _live_capital_blockers(
        runtime_mode=runtime_mode,
        live_trading_enabled=live_trading_enabled,
        execution_state=execution_state,
        execution_authority=execution_authority,
        order_submission=order_submission,
        broker_execution_armed=broker_execution_armed,
        readiness_ready=readiness_ready,
        certification_ready=certification_ready,
        has_platform_authority=bool(platform),
    )
    live_capital_active = not blockers
    broker_name = _text(
        broker.get("selected_broker", broker.get("broker", payload.get("broker"))),
        "NONE",
    )
    governance_state = _upper_text(
        governance.get("governance_state", governance.get("status")),
        _upper_text(platform.get("governance_state"), "REVIEW_REQUIRED"),
    )
    kill_switch_engaged = order_submission not in _ORDER_ALLOWED_STATES
    kill_switch_reason = (
        _text(platform.get("kill_switch_reason"), "")
        or "canonical_order_submission_blocked"
        if kill_switch_engaged
        else ""
    )

    return {
        "payload_version": OPERATIONAL_IDENTITY_VERSION,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "broker": broker_name,
        "mode": runtime_mode,
        "resolved_mode": runtime_mode,
        "runtime_mode": runtime_mode,
        "engine_mode": _upper_text(
            platform.get("engine_mode", session.get("engine_mode")),
            "SAFE",
        ),
        "governance_state": governance_state,
        "session_id": _text(payload.get("session_id", session.get("session_id")), ""),
        "capital_source": (
            "CANONICAL_LIVE_AUTHORITY"
            if live_capital_active
            else "CANONICAL_AUTHORITY_BLOCKED"
        ),
        "live_capital_active": live_capital_active,
        "orders_enabled": False,
        "order_activity_allowed": False,
        "kill_switch_engaged": kill_switch_engaged,
        "kill_switch_reason": kill_switch_reason,
        "broker_connected": _strict_true(broker.get("connected")),
        "broker_execution_armed": broker_execution_armed,
        "broker_readiness_status": broker_readiness_status,
        "certification_status": certification_status,
        "execution_state": execution_state,
        "execution_authority": execution_authority,
        "order_submission": order_submission,
        "live_trading_enabled": live_trading_enabled,
        "authority_blockers": blockers,
        "source_metadata": {
            "source": "dashboard.runtime.operational_identity",
            "authority": "backend.runtime.platform_status",
            "runtime_authority": "backend.runtime.runtime_mode",
            "frontend_safe": True,
            "mobile_controls_ignored": mobile_controls is not None,
            "no_broker_calls": True,
            "no_environment_reads": True,
            "no_filesystem_reads": True,
            "no_order_placement": True,
        },
    }


def build_live_capital_banner_payload(
    operational_identity: Mapping[str, Any] | None = None,
    *,
    dashboard_payload: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    identity = dict(
        operational_identity
        or build_operational_identity_payload(
            dashboard_payload,
            generated_at_utc=generated_at_utc,
        )
    )
    active = bool(identity.get("live_capital_active"))
    return {
        "visible": active,
        "headline": "LIVE CAPITAL ACTIVE" if active else "LIVE CAPITAL BLOCKED",
        "broker": str(identity.get("broker") or "NONE"),
        "mode": str(identity.get("mode") or "DISABLED"),
        "engine_mode": str(identity.get("engine_mode") or "SAFE"),
        "session_id": str(identity.get("session_id") or "pending"),
        "environment_state": str(identity.get("mode") or "DISABLED"),
        "governance_state": str(identity.get("governance_state") or "REVIEW_REQUIRED"),
        "kill_switch_engaged": bool(identity.get("kill_switch_engaged")),
        "authority_blockers": list(identity.get("authority_blockers") or []),
        "warning": (
            "Live capital is active by explicit canonical authority projection only."
            if active
            else "Canonical authority does not permit live capital."
        ),
    }


def _live_capital_blockers(
    *,
    runtime_mode: str,
    live_trading_enabled: bool,
    execution_state: str,
    execution_authority: bool,
    order_submission: str,
    broker_execution_armed: bool,
    readiness_ready: bool,
    certification_ready: bool,
    has_platform_authority: bool,
) -> list[str]:
    blockers: list[str] = []
    if not has_platform_authority:
        blockers.append("missing_platform_authority")
    if runtime_mode not in _LIVE_RUNTIME_MODES:
        blockers.append("runtime_mode_not_live")
    if not live_trading_enabled:
        blockers.append("live_trading_not_enabled")
    if execution_state != "ENABLED" or not execution_authority:
        blockers.append("execution_authority_blocked")
    if order_submission not in _ORDER_ALLOWED_STATES:
        blockers.append("order_submission_blocked")
    if not broker_execution_armed:
        blockers.append("broker_execution_not_armed")
    if not readiness_ready:
        blockers.append("broker_readiness_not_ready")
    if not certification_ready:
        blockers.append("certification_not_ready")
    return blockers


def _runtime_mode(
    platform_status: Mapping[str, Any],
    runtime_resolution: Mapping[str, Any],
) -> str:
    runtime_mode = _upper_text(
        platform_status.get("runtime_mode", runtime_resolution.get("runtime_mode")),
        "DISABLED",
    )
    if runtime_mode not in {"DISABLED", "LIVE", "LIVE_MICRO_PILOT", "LIVE_READ_ONLY", "PAPER"}:
        return "DISABLED"
    return runtime_mode


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _strict_true(value: Any) -> bool:
    return value is True


def _text(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _upper_text(value: Any, default: str) -> str:
    return _text(value, default).upper()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "OPERATIONAL_IDENTITY_VERSION",
    "build_live_capital_banner_payload",
    "build_operational_identity_payload",
]
