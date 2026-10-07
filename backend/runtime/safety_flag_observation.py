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
