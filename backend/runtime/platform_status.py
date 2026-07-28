"""
Phase 177F — Canonical platform status (distinct mode concepts).

Separates:
  A. runtime_mode      — Runtime Mode Resolver only
  B. engine_mode       — strategy posture
  C. broker_mode       — broker environment / account posture
  D. mobile_access_mode — UI permission plane
  E. execution_state   — BLOCKED / SIMULATED / ADVISORY_ONLY / ENABLED
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from backend.runtime.runtime_mode import resolve_runtime_mode

SCHEMA_VERSION = "css.platform_status.v1"

MOBILE_ACCESS_MAP = {
    "MOBILE_READ_ONLY": "READ_ONLY",
    "MOBILE_PAPER_TRADING": "OPERATOR",
    "MOBILE_LIVE_TRADING_ARMED": "OPERATOR",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def mobile_access_mode_from_controls(controls: Mapping[str, Any] | None) -> str:
    raw = str(_mapping(controls).get("mobile_trading_mode") or "MOBILE_READ_ONLY").strip().upper()
    return MOBILE_ACCESS_MAP.get(raw, "READ_ONLY")


def build_platform_status(
    *,
    session: Mapping[str, Any] | None = None,
    broker_startup: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    mobile_controls: Mapping[str, Any] | None = None,
    explicit_mode: Any = None,
) -> dict[str, Any]:
    """Build unified multi-concept status. Runtime mode is resolver-only."""
    session_m = _mapping(session)
    broker_m = _mapping(broker_startup)
    controls = _mapping(mobile_controls)
    resolution = resolve_runtime_mode(
        session=session_m or None,
        broker_startup=broker_m or None,
        evidence=_mapping(evidence) or None,
        explicit_mode=explicit_mode,
    )
    res = resolution.as_dict()

    runtime_mode = str(res.get("runtime_mode") or "DISABLED").upper()
    requested_mode = str(res.get("operator_intent") or explicit_mode or session_m.get("runtime_mode") or "UNSET").strip().upper()
    observed_mode = str(
        broker_m.get("runtime_mode")
        or broker_m.get("broker_mode")
        or res.get("environment_profile")
        or res.get("broker_mode")
        or "UNAVAILABLE"
    ).strip().upper()
    execution_enabled = bool(res.get("execution_enabled"))
    execution_authority = str(res.get("execution_authority") or "BLOCKED").upper()
    if execution_enabled and execution_authority not in {"BLOCKED", "FALSE", "0"}:
        execution_state = "ENABLED"
    else:
        execution_state = "BLOCKED"

    engine_mode = (
        str(controls.get("engine_mode") or "").strip().upper()
        or str(session_m.get("engine_mode") or "").strip().upper()
        or str(res.get("engine_mode") or "").strip().upper()
        or "UNKNOWN"
    )
    if engine_mode not in {"SAFE", "CONSERVATIVE", "BALANCED", "AGGRESSIVE", "EXPANSION", "UNKNOWN"}:
        engine_mode = "UNKNOWN"

    broker_mode = (
        str(res.get("broker_mode") or "").strip().upper()
        or str(broker_m.get("broker_mode") or broker_m.get("mode") or "").strip().upper()
        or "NONE"
    )
    if not broker_mode:
        broker_mode = "NONE"

    mobile_access = mobile_access_mode_from_controls(controls) if controls else "READ_ONLY"
    generated_at = _utc_now()
    reason = str(res.get("reason") or "runtime_mode_unavailable")
    disagreement = any("conflict" in str(item).lower() for item in res.get("resolution_chain") or []) or "conflict" in reason.lower()
    if runtime_mode == "PAPER":
        broker_posture = "PAPER"
    elif runtime_mode == "LIVE_READ_ONLY":
        broker_posture = "READ_ONLY"
    elif runtime_mode in {"LIVE", "LIVE_MICRO_PILOT"}:
        broker_posture = "LIVE_BLOCKED"
    elif runtime_mode == "DISABLED":
        broker_posture = "DISABLED"
    else:
        broker_posture = "UNKNOWN"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "requested_mode": requested_mode,
        "observed_mode": observed_mode,
        "effective_mode": runtime_mode,
        "runtime_mode": runtime_mode,
        "runtime_mode_reason": reason,
        "fail_closed": bool(res.get("fail_closed", True)),
        "execution_authority": False if execution_state == "BLOCKED" else bool(execution_enabled),
        "execution_authority_label": execution_authority,
        "execution_state": execution_state,
        "execution_posture": "DISABLED" if execution_state == "BLOCKED" else "ENABLED",
        "order_submission": res.get("order_submission") or "BLOCKED",
        "engine_mode": engine_mode,
        "broker_mode": broker_mode,
        "broker_posture": broker_posture,
        "mobile_access_mode": mobile_access,
        "mobile_trading_mode": str(controls.get("mobile_trading_mode") or "MOBILE_READ_ONLY").upper()
        if controls
        else "MOBILE_READ_ONLY",
        "operator_intent": res.get("operator_intent") or "UNSET",
        "environment_profile": res.get("environment_profile"),
        "advisory_only": True,
        "live_trading_enabled": False,
        # Compatibility alias — MUST equal canonical runtime_mode (never mobile-access derived).
        "system_mode": runtime_mode,
        "system_mode_deprecated": True,
        "system_mode_migration": "Use runtime_mode; system_mode is a compatibility alias equal to runtime_mode",
        "source": "RUNTIME_MODE_RESOLVER",
        "source_freshness": "CURRENT",
        "source_confidence": "LOW" if runtime_mode == "DISABLED" or disagreement else "HIGH",
        "source_disagreement": disagreement,
        "degraded_reason": reason if runtime_mode in {"DISABLED", "UNKNOWN", "UNAVAILABLE"} or disagreement else "",
        "provenance": {
            "runtime_mode": "RUNTIME_MODE_RESOLVER",
            "engine_mode": "MOBILE_CONTROLS|SESSION|RESOLVER" if controls or session_m else "UNKNOWN",
            "broker_mode": "BROKER_REGISTRY|RESOLVER",
            "mobile_access_mode": "MOBILE_CONTROLS",
            "execution_state": "RUNTIME_MODE_RESOLVER|DERIVED",
        },
        "resolution_chain": res.get("resolution_chain") or [],
        "generated_at": generated_at,
    }
    return payload


__all__ = [
    "SCHEMA_VERSION",
    "build_platform_status",
    "mobile_access_mode_from_controls",
]
