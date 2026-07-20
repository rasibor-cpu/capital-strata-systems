"""
Phase 177A — Canonical Runtime Mode Resolver.

Single authoritative runtime-mode service for CSS startup and UI surfaces.

Supported modes ONLY:
  PAPER | LIVE_READ_ONLY | LIVE_MICRO_PILOT | LIVE | DISABLED

Rules:
  - No silent PAPER fallback when resolution is incomplete → DISABLED
  - LIVE_READ_ONLY ⇒ execution_enabled=False (orders blocked)
  - LIVE / LIVE_MICRO_PILOT still require existing institutional authority gates;
    this phase does NOT enable live trading by itself
  - Does not invent subsystem-specific mode vocabularies

Orchestration only — does not weaken live_execution_authority or broker profiles.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from backend.runtime.broker_environment_profiles import (
    BrokerEnvironmentProfile,
    profile_mode_alias,
    select_broker_environment_profile,
)

SCHEMA_VERSION = "css.runtime_mode.v1"

OPERATOR_INTENT_KEYS = (
    "CSS_RUNTIME_MODE",
    "CSS_OPERATOR_RUNTIME_MODE",
    "RUNTIME_MODE",
    "OPERATOR_RUNTIME_MODE",
)

MICRO_PILOT_KEYS = (
    "CSS_LIVE_MICRO_PILOT",
    "LIVE_MICRO_PILOT",
    "CSS_LIVE_MICRO_PILOT_ARMED",
)


class RuntimeMode(str, Enum):
    PAPER = "PAPER"
    LIVE_READ_ONLY = "LIVE_READ_ONLY"
    LIVE_MICRO_PILOT = "LIVE_MICRO_PILOT"
    LIVE = "LIVE"
    DISABLED = "DISABLED"


# Modes subsystems must not invent outside this set
SUPPORTED_RUNTIME_MODES = frozenset(m.value for m in RuntimeMode)


@dataclass(frozen=True)
class RuntimeModeResolution:
    runtime_mode: RuntimeMode
    execution_enabled: bool
    execution_authority: str
    order_submission: str
    reason: str
    resolution_chain: tuple[str, ...] = field(default_factory=tuple)
    operator_intent: str | None = None
    environment_profile: str | None = None
    broker_mode: str | None = None
    engine_mode: str | None = None  # SAFE/BALANCED/... — strategy posture, NOT runtime mode
    fail_closed: bool = True
    advisory_only: bool = True
    trading_impact: bool = False
    generated_at: str = ""
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["runtime_mode"] = self.runtime_mode.value
        payload["resolution_chain"] = list(self.resolution_chain)
        payload["generated_at"] = self.generated_at or _utc_now()
        payload["supported_modes"] = sorted(SUPPORTED_RUNTIME_MODES)
        payload["live_trading_enabled"] = False  # Phase 177A: never auto-enable
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "armed", "enabled"}


def normalize_runtime_mode(value: Any) -> RuntimeMode | None:
    """Map aliases into the canonical five-mode set. Unknown → None (caller fail-closes)."""
    if isinstance(value, RuntimeMode):
        return value
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not text:
        return None
    aliases = {
        "PAPER": RuntimeMode.PAPER,
        "PRACTICE": RuntimeMode.PAPER,
        "SIM": RuntimeMode.PAPER,
        "SIMULATED": RuntimeMode.PAPER,
        "SIMULATION": RuntimeMode.PAPER,
        "PAPER_ONLY": RuntimeMode.PAPER,
        "LIVE_READ_ONLY": RuntimeMode.LIVE_READ_ONLY,
        "LIVE_READONLY": RuntimeMode.LIVE_READ_ONLY,
        "READ_ONLY": RuntimeMode.LIVE_READ_ONLY,
        "READONLY": RuntimeMode.LIVE_READ_ONLY,
        "LIVE_READ_ONLY_VALIDATION": RuntimeMode.LIVE_READ_ONLY,
        "LIVE_MICRO_PILOT": RuntimeMode.LIVE_MICRO_PILOT,
        "MICRO_PILOT": RuntimeMode.LIVE_MICRO_PILOT,
        "LIVE_MICRO": RuntimeMode.LIVE_MICRO_PILOT,
        "LIVE": RuntimeMode.LIVE,
        "LIVE_EXECUTION": RuntimeMode.LIVE,
        "EXECUTION": RuntimeMode.LIVE,
        "DISABLED": RuntimeMode.DISABLED,
        "OFF": RuntimeMode.DISABLED,
        "NONE": RuntimeMode.DISABLED,
        "UNAVAILABLE": RuntimeMode.DISABLED,
        "UNKNOWN": RuntimeMode.DISABLED,
    }
    # Engine strategy modes are NOT runtime modes
    if text in {"SAFE", "BALANCED", "AGGRESSIVE", "EXPANSION", "CONSERVATIVE"}:
        return None
    return aliases.get(text)


def _profile_to_runtime_mode(profile: BrokerEnvironmentProfile | None) -> RuntimeMode | None:
    if profile is None:
        return None
    if profile == BrokerEnvironmentProfile.PAPER:
        return RuntimeMode.PAPER
    if profile == BrokerEnvironmentProfile.LIVE_READ_ONLY:
        return RuntimeMode.LIVE_READ_ONLY
    if profile == BrokerEnvironmentProfile.LIVE_EXECUTION:
        return RuntimeMode.LIVE
    return None


def _read_operator_intent(env: Mapping[str, Any], explicit: Any = None) -> tuple[RuntimeMode | None, str | None]:
    if explicit is not None and str(explicit).strip():
        mode = normalize_runtime_mode(explicit)
        return mode, str(explicit).strip()
    for key in OPERATOR_INTENT_KEYS:
        raw = env.get(key)
        if raw is not None and str(raw).strip():
            return normalize_runtime_mode(raw), str(raw).strip()
    return None, None


def _micro_pilot_requested(env: Mapping[str, Any], evidence: Mapping[str, Any]) -> bool:
    for key in MICRO_PILOT_KEYS:
        if _truthy(env.get(key)):
            return True
    if _truthy(evidence.get("live_micro_pilot_armed")):
        return True
    if str(evidence.get("live_micro_pilot_state") or "").upper() in {"ARMED", "ACTIVE", "ENABLED"}:
        return True
    return False


def resolve_runtime_mode(
    *,
    env: Mapping[str, Any] | None = None,
    explicit_mode: Any = None,
    session: Mapping[str, Any] | None = None,
    broker_startup: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    allow_implicit_paper: bool = False,
) -> RuntimeModeResolution:
    """
    Canonical resolution order:

    Operator Intent
      → Environment Configuration (broker environment profile)
      → Broker Selection / broker_mode signals
      → Micro-pilot arming signals
      → Safety / completeness gates
      → Execution authority projection (never enabling LIVE trading alone)

    Incomplete / conflicting / unknown ⇒ DISABLED (fail-closed).
    Silent PAPER fallback is forbidden unless allow_implicit_paper=True
    (reserved for explicit paper operator paths / tests only).
    """
    source_env = env if isinstance(env, Mapping) else os.environ
    sess = session if isinstance(session, Mapping) else {}
    startup = broker_startup if isinstance(broker_startup, Mapping) else {}
    ev = evidence if isinstance(evidence, Mapping) else {}
    chain: list[str] = []

    intent_mode, intent_raw = _read_operator_intent(source_env, explicit_mode)
    if intent_raw:
        chain.append(f"operator_intent:{intent_raw}")
    if intent_mode is RuntimeMode.DISABLED:
        return _disabled("operator_intent_disabled", chain, intent_raw=intent_raw)

    # Session explicit runtime_mode (not engine strategy mode)
    session_runtime = normalize_runtime_mode(sess.get("runtime_mode"))
    if session_runtime is None and sess.get("runtime_mode"):
        # Reject engine_mode masquerading as runtime_mode
        chain.append(f"session_runtime_mode_rejected:{sess.get('runtime_mode')}")
    elif session_runtime is not None:
        chain.append(f"session_runtime_mode:{session_runtime.value}")
        if intent_mode is None:
            intent_mode = session_runtime

    profile = select_broker_environment_profile(env=source_env)
    profile_mode = _profile_to_runtime_mode(profile)
    if profile is not None:
        chain.append(f"broker_environment_profile:{profile.value}")
    else:
        # Attempt legacy mode alias from CSS_BROKER_* without inventing PAPER
        legacy = profile_mode_alias(str(source_env.get("CSS_BROKER_MODE") or source_env.get("BROKER_MODE") or ""))
        if legacy is not None:
            profile = legacy
            profile_mode = _profile_to_runtime_mode(legacy)
            chain.append(f"legacy_broker_mode_alias:{legacy.value}")

    broker_mode_raw = str(startup.get("broker_mode") or sess.get("broker_mode") or "").strip().lower()
    if broker_mode_raw:
        chain.append(f"broker_mode:{broker_mode_raw}")

    micro = _micro_pilot_requested(source_env, {**dict(startup), **dict(ev)})
    if micro:
        chain.append("micro_pilot_signal:armed")

    # Completeness: need either explicit operator intent OR explicit profile selection
    if intent_mode is None and profile_mode is None and not allow_implicit_paper:
        # broker_mode alone is insufficient to imply PAPER silently when profile missing
        if broker_mode_raw in {"paper", "live"} and profile_mode is None and intent_mode is None:
            return _disabled(
                "incomplete_startup_no_canonical_runtime_mode",
                chain + ["fail_closed:missing_operator_or_profile"],
                intent_raw=intent_raw,
                profile=profile,
                broker_mode=broker_mode_raw or None,
                engine_mode=_engine_mode(sess, startup),
            )
        if not broker_mode_raw and not sess and not startup:
            return _disabled(
                "incomplete_startup_information",
                chain + ["fail_closed:empty_context"],
                intent_raw=intent_raw,
                profile=profile,
                engine_mode=_engine_mode(sess, startup),
            )

    # Resolve candidate
    candidate = intent_mode or profile_mode
    if candidate is None and allow_implicit_paper:
        candidate = RuntimeMode.PAPER
        chain.append("implicit_paper_allowed:test_or_explicit_paper_path")
    if candidate is None:
        return _disabled(
            "unresolved_runtime_mode",
            chain + ["fail_closed:unresolved"],
            intent_raw=intent_raw,
            profile=profile,
            broker_mode=broker_mode_raw or None,
            engine_mode=_engine_mode(sess, startup),
        )

    # Conflict: operator LIVE vs profile PAPER (or vice versa) → DISABLED
    if intent_mode and profile_mode and intent_mode != profile_mode:
        # LIVE vs LIVE_READ_ONLY is a controlled refinement, not a hard conflict
        live_family = {RuntimeMode.LIVE, RuntimeMode.LIVE_READ_ONLY, RuntimeMode.LIVE_MICRO_PILOT}
        if not (intent_mode in live_family and profile_mode in live_family):
            return _disabled(
                f"conflicting_runtime_signals:{intent_mode.value}_vs_{profile_mode.value}",
                chain + ["fail_closed:conflict"],
                intent_raw=intent_raw,
                profile=profile,
                broker_mode=broker_mode_raw or None,
                engine_mode=_engine_mode(sess, startup),
            )

    # Micro-pilot elevates LIVE_READ_ONLY/LIVE intent when armed and profile allows live family
    if micro and candidate in {RuntimeMode.LIVE, RuntimeMode.LIVE_READ_ONLY, RuntimeMode.LIVE_MICRO_PILOT}:
        candidate = RuntimeMode.LIVE_MICRO_PILOT
        chain.append("resolved:LIVE_MICRO_PILOT")
    elif profile_mode == RuntimeMode.LIVE_READ_ONLY and candidate == RuntimeMode.LIVE:
        # Profile read-only caps LIVE intent
        candidate = RuntimeMode.LIVE_READ_ONLY
        chain.append("capped_by_profile:LIVE_READ_ONLY")
    else:
        chain.append(f"resolved:{candidate.value}")

    execution_enabled, authority, order_sub, reason = _execution_projection(candidate, startup, ev, chain)
    return RuntimeModeResolution(
        runtime_mode=candidate,
        execution_enabled=execution_enabled,
        execution_authority=authority,
        order_submission=order_sub,
        reason=reason,
        resolution_chain=tuple(chain),
        operator_intent=intent_raw,
        environment_profile=profile.value if profile else None,
        broker_mode=broker_mode_raw or None,
        engine_mode=_engine_mode(sess, startup),
        fail_closed=True,
        generated_at=_utc_now(),
    )


def _engine_mode(session: Mapping[str, Any], startup: Mapping[str, Any]) -> str | None:
    for source in (session, startup):
        value = source.get("engine_mode")
        text = str(value or "").strip().upper()
        if text in {"SAFE", "BALANCED", "AGGRESSIVE", "EXPANSION", "CONSERVATIVE"}:
            return text
    return None


def _execution_projection(
    mode: RuntimeMode,
    startup: Mapping[str, Any],
    evidence: Mapping[str, Any],
    chain: list[str],
) -> tuple[bool, str, str, str]:
    """
    Project execution flags. Phase 177A never enables live trading on its own.
    LIVE_READ_ONLY / PAPER / DISABLED ⇒ always blocked.
    LIVE / LIVE_MICRO_PILOT ⇒ still BLOCKED here; authority layers remain authoritative.
    """
    if mode in {RuntimeMode.DISABLED, RuntimeMode.PAPER, RuntimeMode.LIVE_READ_ONLY}:
        reason = {
            RuntimeMode.DISABLED: "runtime_mode_disabled",
            RuntimeMode.PAPER: "paper_mode_orders_simulated_only",
            RuntimeMode.LIVE_READ_ONLY: "live_read_only_execution_blocked",
        }[mode]
        chain.append(f"execution:{reason}")
        return False, "BLOCKED", "BLOCKED", reason

    # LIVE / LIVE_MICRO_PILOT: report blocked unless existing authority evidence already grants
    # AND we still force trading_impact false at this layer (do not enable live trading here).
    auth_state = str(
        evidence.get("live_authority_state")
        or startup.get("live_authority_state")
        or "BLOCKED"
    ).upper()
    can_exec = bool(evidence.get("can_live_execute") or startup.get("can_live_execute"))
    # Phase 177A hard rule: resolver does not flip execution on
    chain.append("execution:live_family_requires_authority_layers_still_blocked_by_177a")
    return False, auth_state if auth_state else "BLOCKED", "BLOCKED", "live_execution_not_enabled_by_runtime_mode_resolver"


def _disabled(
    reason: str,
    chain: list[str],
    *,
    intent_raw: str | None = None,
    profile: BrokerEnvironmentProfile | None = None,
    broker_mode: str | None = None,
    engine_mode: str | None = None,
) -> RuntimeModeResolution:
    return RuntimeModeResolution(
        runtime_mode=RuntimeMode.DISABLED,
        execution_enabled=False,
        execution_authority="BLOCKED",
        order_submission="BLOCKED",
        reason=reason,
        resolution_chain=tuple(chain),
        operator_intent=intent_raw,
        environment_profile=profile.value if profile else None,
        broker_mode=broker_mode,
        engine_mode=engine_mode,
        fail_closed=True,
        generated_at=_utc_now(),
    )


class RuntimeModeResolver:
    """Service facade — every subsystem should query this (or resolve_runtime_mode)."""

    def resolve(self, **kwargs: Any) -> RuntimeModeResolution:
        return resolve_runtime_mode(**kwargs)

    def as_dict(self, **kwargs: Any) -> dict[str, Any]:
        return self.resolve(**kwargs).as_dict()


def get_runtime_mode_resolver() -> RuntimeModeResolver:
    return RuntimeModeResolver()
