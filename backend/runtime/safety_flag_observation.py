"""Observed (not asserted) execution safety flags for runtime endpoints and evidence.

Derives the four CSS safety flags from independent runtime sources instead of
publishing literals. Any source that cannot be read makes the dependent flags
``None`` (not observed), which every evidence consumer treats as a hard failure.
Read-only: never changes any flag or control.

- ``execution_allowed``      -- runtime-mode execution_enabled, or broker
                                execution_authority / can_live_execute
- ``broker_execution_armed`` -- mobile live-trading control armed, legacy
                                dashboard BROKER_EXECUTION_ARMED, or can_live_execute
- ``live_trading_blocked``   -- no live signal from any source (incl. LIVE /
                                LIVE_MICRO_PILOT runtime mode)
- ``advisory_only``          -- runtime-mode advisory_only is literally True and
                                execution is not allowed
"""
from __future__ import annotations

from typing import Any, Mapping

LIVE_RUNTIME_MODES = frozenset({"LIVE", "LIVE_MICRO_PILOT"})
MOBILE_ARMED_MODE = "MOBILE_LIVE_TRADING_ARMED"
FLAG_NAMES = ("execution_allowed", "live_trading_blocked", "broker_execution_armed", "advisory_only")


def derive_safety_flags(
    *,
    runtime_mode: Mapping[str, Any] | None,
    authority: Mapping[str, Any] | None,
    mobile_trading_mode: str | None,
    legacy_broker_execution_armed: Any,
) -> dict[str, Any]:
    unknown: list[str] = []
    if not isinstance(runtime_mode, Mapping) or "runtime_mode" not in runtime_mode:
        unknown.append("runtime_mode")
    if not isinstance(authority, Mapping):
        unknown.append("live_execution_authority")
    if not isinstance(mobile_trading_mode, str) or not mobile_trading_mode.strip():
        unknown.append("mobile_trading_mode")
    if legacy_broker_execution_armed is not None and type(legacy_broker_execution_armed) is not bool:
        unknown.append("legacy_broker_execution_armed")

    sources = {
        "runtime_mode": dict(runtime_mode) if isinstance(runtime_mode, Mapping) else None,
        "live_execution_authority": dict(authority) if isinstance(authority, Mapping) else None,
        "mobile_trading_mode": mobile_trading_mode,
        "legacy_broker_execution_armed": legacy_broker_execution_armed,
    }
    if unknown:
        return {**{name: None for name in FLAG_NAMES}, "observed": False,
                "unknown_sources": unknown, "sources": _summary(sources)}

    rm = runtime_mode or {}
    au = authority or {}
    mode = str(rm.get("runtime_mode") or "").strip().upper()
    execution_allowed = (rm.get("execution_enabled") is True or au.get("execution_authority") is True
                         or au.get("can_live_execute") is True)
    armed = (mobile_trading_mode.strip().upper() == MOBILE_ARMED_MODE
             or legacy_broker_execution_armed is True or au.get("can_live_execute") is True)
    live_signal = execution_allowed or armed or mode in LIVE_RUNTIME_MODES
    return {
        "execution_allowed": execution_allowed,
        "live_trading_blocked": not live_signal,
        "broker_execution_armed": armed,
        "advisory_only": rm.get("advisory_only") is True and not execution_allowed,
        "observed": True,
        "unknown_sources": [],
        "sources": _summary(sources),
    }


def _summary(sources: Mapping[str, Any]) -> dict[str, Any]:
    rm = sources.get("runtime_mode") or {}
    au = sources.get("live_execution_authority") or {}
    return {
        "runtime_mode": rm.get("runtime_mode"),
        "runtime_execution_enabled": rm.get("execution_enabled"),
        "runtime_advisory_only": rm.get("advisory_only"),
        "authority_execution_authority": au.get("execution_authority"),
        "authority_can_live_execute": au.get("can_live_execute"),
        "mobile_trading_mode": sources.get("mobile_trading_mode"),
        "legacy_broker_execution_armed": sources.get("legacy_broker_execution_armed"),
    }


# ---- authoritative read-only status surface (GET /api/v1/safety-flags) --------

SAFETY_FLAGS_ENDPOINT = "/api/v1/safety-flags"
SAFETY_FLAGS_SCHEMA = "css.safety_flags.v1"
NOT_OBSERVED = "NOT_OBSERVED"
REQUIRED_SAFE_VALUES: dict[str, bool] = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
}


def authoritative_safety_flags_payload(derived: Mapping[str, Any] | None, *, observed_at: str) -> dict[str, Any]:
    """The single authoritative flag surface. Each flag is an exact bool or ``"NOT_OBSERVED"``.

    ``verdict`` is ``SAFE`` only when all four are observed with the required values;
    any missing flag gives ``NOT_OBSERVED`` and any other value gives ``UNSAFE``.
    Never infers a safe value.
    """
    derived = derived if isinstance(derived, Mapping) else {}
    flags: dict[str, Any] = {}
    not_observed: list[str] = []
    unsafe: list[str] = []
    for name, required in REQUIRED_SAFE_VALUES.items():
        value = derived.get(name)
        if type(value) is not bool:
            flags[name] = NOT_OBSERVED
            not_observed.append(name)
        else:
            flags[name] = value
            if value is not required:
                unsafe.append(name)
    verdict = NOT_OBSERVED if not_observed else ("UNSAFE" if unsafe else "SAFE")
    return {
        "schema": SAFETY_FLAGS_SCHEMA,
        **flags,
        "verdict": verdict,
        "fail_closed": verdict != "SAFE",
        "not_observed": not_observed,
        "unsafe": unsafe,
        "required": dict(REQUIRED_SAFE_VALUES),
        "unknown_sources": list(derived.get("unknown_sources") or []),
        "sources": derived.get("sources"),
        "read_only": True,
        "observed_at_utc": observed_at,
    }
