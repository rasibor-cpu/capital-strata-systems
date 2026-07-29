"""Fail-closed web kill-switch request governance."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

WEB_KILL_SWITCH_GOVERNANCE_VERSION = "css.web_kill_switch_governance.v2"
WEB_KILL_SWITCH_AUDIT_SCHEMA_VERSION = "css.web_kill_switch_governance.audit.v1"
WEB_KILL_SWITCH_CONFIRMATION_TOKEN = "ENGAGE_KILL_SWITCH"
WEB_KILL_SWITCH_SOURCE_PAGE = "/dashboard"
WEB_KILL_SWITCH_SOURCE_API = "/api/v1/web-kill-switch/governance"

ACTION_ENGAGE = "ENGAGE"
ACTION_ACKNOWLEDGE = "ACKNOWLEDGE"
ACTION_REQUEST_RELEASE = "REQUEST_RELEASE"
ACTION_CANCEL_REQUEST = "CANCEL_REQUEST"

DECISION_APPROVED = "APPROVED_FOR_CANONICAL_PROCESSING"
DECISION_REJECTED = "REJECTED"
DECISION_BLOCKED = "BLOCKED"
DECISION_INVALID = "INVALID"
DECISION_PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
DECISION_CANONICAL_UNAVAILABLE = "CANONICAL_STATE_UNAVAILABLE"

_SUPPORTED_ACTIONS = frozenset(
    {
        ACTION_ENGAGE,
        ACTION_ACKNOWLEDGE,
        ACTION_REQUEST_RELEASE,
        ACTION_CANCEL_REQUEST,
    }
)
_ACTION_CONFIRMATION_TOKENS = {
    ACTION_ENGAGE: WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
    ACTION_ACKNOWLEDGE: "ACKNOWLEDGE_KILL_SWITCH",
    ACTION_REQUEST_RELEASE: "REQUEST_KILL_SWITCH_RELEASE",
    ACTION_CANCEL_REQUEST: "CANCEL_KILL_SWITCH_REQUEST",
}
_RELEASE_ALLOWED_STATES = frozenset({"RELEASE_REVIEW_PERMITTED", "READY_FOR_RELEASE_REVIEW"})
_READY_STATES = frozenset({"PASS", "PASSED", "READY", "GREEN", "CERTIFIED"})
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "private",
    "secret",
    "token",
)
_SENSITIVE_VALUE_MARKERS = (
    "api_key=",
    "apikey=",
    "authorization:",
    "bearer ",
    "password=",
    "private key",
    "secret=",
    "token=",
)
_SAFETY_DISCLAIMER = (
    "Web kill-switch governance validates operator requests only. It does not "
    "write state, clear canonical kill switches, arm brokers, enable orders, or "
    "mutate runtime, platform, audit, replay, or certification stores."
)


def build_web_kill_switch_status_payload(
    *,
    canonical_state: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    state = _mapping(canonical_state)
    supplied = bool(state)
    engaged = state.get("engaged") is True or state.get("blocked") is True
    return {
        "payload_version": WEB_KILL_SWITCH_GOVERNANCE_VERSION,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "canonical_state_supplied": supplied,
        "canonical_effective_state": "ENGAGED" if engaged else "UNCONFIRMED",
        "canonical_application_status": "SUPPLIED" if supplied else "UNCONFIRMED",
        "engaged": engaged if supplied else True,
        "reason": _safe_text(state.get("reason")) if supplied else "canonical_state_unavailable",
        "source": _safe_text(state.get("source")) if supplied else "fail_closed_projection",
        "orders_enabled": False,
        "broker_execution_armed": False,
        "execution_allowed": False,
        "trading_armed": False,
        "confirmation_token_required": WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
        "governance": _governance_flags(),
        "safety_disclaimer": _SAFETY_DISCLAIMER,
        "source_metadata": _source_metadata(),
    }


def evaluate_web_kill_switch_governance_request(
    request: Mapping[str, Any] | None,
    *,
    canonical_state: Mapping[str, Any] | None = None,
    duplicate_context: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    created_at = generated_at_utc or _utc_now()
    source = _mapping(request)
    action = _action(source.get("action"))
    resolved_request_id = _safe_text(source.get("request_id") or request_id)
    operator_id = _operator(source.get("operator_id"))
    reason = _reason(source.get("reason"))
    confirmation = _confirmation(source.get("confirmation"), action)
    canonical = _mapping(canonical_state)
    duplicate = _mapping(duplicate_context)

    blockers = _base_blockers(
        action=action,
        request_id=resolved_request_id,
        operator_id=operator_id,
        reason=reason,
        confirmation=confirmation,
        raw_request=source,
    )
    decision = _decision_for_base(action, blockers, confirmation)
    if not blockers and action == ACTION_REQUEST_RELEASE:
        release_blockers = _release_blockers(canonical)
        blockers.extend(release_blockers)
        decision = DECISION_APPROVED if not blockers else DECISION_BLOCKED
    elif not blockers and action == ACTION_ENGAGE:
        decision = DECISION_APPROVED
    elif not blockers:
        decision = DECISION_APPROVED

    duplicate_blocker = _duplicate_blocker(source, duplicate)
    if duplicate_blocker:
        blockers.append(duplicate_blocker)
        decision = DECISION_REJECTED

    canonical_application = _canonical_application_status(canonical)
    envelope = {
        "schema_version": WEB_KILL_SWITCH_AUDIT_SCHEMA_VERSION,
        "payload_version": WEB_KILL_SWITCH_GOVERNANCE_VERSION,
        "request_id": resolved_request_id,
        "requested_action": action,
        "governance_decision": decision,
        "operator_id": operator_id,
        "reason": reason,
        "confirmation": confirmation,
        "canonical_state_supplied": bool(canonical),
        "canonical_effective_state": _canonical_effective_state(canonical),
        "canonical_application_status": canonical_application,
        "blocking_reasons": blockers,
        "created_at_utc": created_at,
        "evaluated_at_utc": created_at,
        "source_channel": _safe_text(source.get("source_channel")) or "web",
        "correlation_id": _safe_text(source.get("correlation_id")),
        "orders_enabled": False,
        "broker_execution_armed": False,
        "execution_allowed": False,
        "trading_armed": False,
        "position_close_performed": False,
        "effective_state_changed": False,
        "audit_recorded": False,
        "audit_record": {},
        "governance": _governance_flags(),
        "safety_disclaimer": _SAFETY_DISCLAIMER,
        "source_metadata": _source_metadata(),
    }
    envelope["governance_hash"] = _stable_hash(envelope)
    return envelope


def engage_web_kill_switch(
    *,
    operator_id: str,
    confirmation_token: str,
    reason: str = "",
    ledger: Any | None = None,
    generated_at_utc: str | None = None,
    request_id: str | None = None,
    canonical_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del ledger
    return evaluate_web_kill_switch_governance_request(
        {
            "action": ACTION_ENGAGE,
            "operator_id": operator_id,
            "reason": reason,
            "request_id": request_id,
            "confirmation": {
                "confirmed": True,
                "action": ACTION_ENGAGE,
                "token": confirmation_token,
            },
            "source_channel": "web",
        },
        canonical_state=canonical_state,
        generated_at_utc=generated_at_utc,
    )


def build_kill_switch_audit_preview(
    *,
    generated_at_utc: str | None = None,
    request_id: str = "PREVIEW-KILL-SWITCH",
) -> dict[str, Any]:
    return evaluate_web_kill_switch_governance_request(
        {
            "action": ACTION_ENGAGE,
            "operator_id": "preview-only",
            "reason": "preview record only; not an engagement",
            "request_id": request_id,
            "confirmation": {
                "confirmed": True,
                "action": ACTION_ENGAGE,
                "token": WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
            },
            "source_channel": "preview",
        },
        generated_at_utc=generated_at_utc,
    )


def _base_blockers(
    *,
    action: str,
    request_id: str,
    operator_id: str,
    reason: str,
    confirmation: Mapping[str, Any],
    raw_request: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not action:
        blockers.append("action_missing")
    elif action not in _SUPPORTED_ACTIONS:
        blockers.append("action_unsupported")
    if not request_id:
        blockers.append("request_id_missing")
    elif not _bounded_identifier(request_id, max_length=80):
        blockers.append("request_id_invalid")
    if not operator_id:
        blockers.append("operator_id_missing")
    if not reason:
        blockers.append("reason_missing")
    if confirmation.get("status") != "CONFIRMED":
        blockers.append(str(confirmation.get("reason") or "confirmation_invalid"))
    if _contains_sensitive(_request_without_confirmation_token(raw_request)):
        blockers.append("sensitive_payload_rejected")
    return blockers


def _decision_for_base(
    action: str,
    blockers: list[str],
    confirmation: Mapping[str, Any],
) -> str:
    if not blockers:
        return DECISION_APPROVED
    if "confirmation_missing" in blockers and action in _SUPPORTED_ACTIONS:
        return DECISION_PENDING_CONFIRMATION
    if "action_missing" in blockers or "action_unsupported" in blockers:
        return DECISION_INVALID
    if str(confirmation.get("reason") or "").startswith("confirmation_action_mismatch"):
        return DECISION_REJECTED
    return DECISION_REJECTED


def _release_blockers(canonical_state: Mapping[str, Any]) -> list[str]:
    if not canonical_state:
        return ["canonical_release_authority_missing"]
    blockers: list[str] = []
    release_state = _upper(canonical_state.get("release_review_state"))
    readiness = _upper(canonical_state.get("readiness_status"))
    certification = _upper(canonical_state.get("certification_status"))
    incident = _upper(canonical_state.get("incident_status"))
    contradiction = canonical_state.get("contradictory") is True

    if release_state not in _RELEASE_ALLOWED_STATES:
        blockers.append("release_review_not_permitted")
    if readiness not in _READY_STATES:
        blockers.append("readiness_not_passed")
    if certification not in _READY_STATES:
        blockers.append("certification_not_passed")
    if incident not in {"CLEARED", "NONE", "RESOLVED"}:
        blockers.append("blocking_incident_active")
    if contradiction:
        blockers.append("canonical_state_contradictory")
    if canonical_state.get("malformed") is True:
        blockers.append("canonical_state_malformed")
    return blockers


def _duplicate_blocker(
    request: Mapping[str, Any],
    duplicate_context: Mapping[str, Any],
) -> str:
    if not duplicate_context:
        return ""
    previous = _mapping(duplicate_context.get("request"))
    if not previous:
        return ""
    comparable = _request_fingerprint(request)
    previous_comparable = _request_fingerprint(previous)
    if comparable == previous_comparable:
        return ""
    if _safe_text(previous.get("request_id")) == _safe_text(request.get("request_id")):
        return "duplicate_request_id_conflict"
    return ""


def _request_fingerprint(request: Mapping[str, Any]) -> str:
    safe = {
        "request_id": _safe_text(request.get("request_id")),
        "action": _action(request.get("action")),
        "operator_id": _operator(request.get("operator_id")),
        "reason": _reason(request.get("reason")),
        "confirmation": _mapping(request.get("confirmation")),
    }
    return _stable_hash(safe)


def _request_without_confirmation_token(request: Mapping[str, Any]) -> dict[str, Any]:
    safe = dict(request)
    confirmation = _mapping(safe.get("confirmation"))
    if confirmation:
        safe["confirmation"] = {
            key: item
            for key, item in confirmation.items()
            if str(key).strip().lower() != "token"
        }
    return safe


def _confirmation(value: Any, action: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {
            "confirmed": False,
            "status": "REJECTED",
            "reason": "confirmation_missing",
        }
    confirmed = value.get("confirmed") is True
    confirmation_action = _action(value.get("action"))
    token = _safe_text(value.get("token"))
    expected_token = _ACTION_CONFIRMATION_TOKENS.get(action, "")
    if not confirmed:
        return {
            "confirmed": False,
            "status": "REJECTED",
            "reason": "confirmation_boolean_invalid",
        }
    if confirmation_action != action:
        return {
            "confirmed": False,
            "status": "REJECTED",
            "reason": "confirmation_action_mismatch",
        }
    if not expected_token or token != expected_token:
        return {
            "confirmed": False,
            "status": "REJECTED",
            "reason": "confirmation_token_invalid",
        }
    return {
        "confirmed": True,
        "status": "CONFIRMED",
        "reason": "",
        "action": action,
    }


def _canonical_application_status(canonical_state: Mapping[str, Any]) -> str:
    if canonical_state.get("application_confirmed") is True:
        return "CONFIRMED_BY_CANONICAL_AUTHORITY"
    return "UNCONFIRMED"


def _canonical_effective_state(canonical_state: Mapping[str, Any]) -> str:
    if not canonical_state:
        return "UNAVAILABLE"
    if canonical_state.get("engaged") is True or canonical_state.get("blocked") is True:
        return "ENGAGED"
    if canonical_state.get("engaged") is False and canonical_state.get("blocked") is False:
        return "DISENGAGED_SUPPLIED"
    return "UNKNOWN"


def _governance_flags() -> dict[str, Any]:
    return {
        "request_validator": True,
        "governance_policy_evaluator": True,
        "read_only_projection": True,
        "command_envelope_builder": True,
        "audit_record_builder": True,
        "canonical_execution_authority": False,
        "broker_mutation_allowed": False,
        "execution_allowed": False,
        "orders_enabled": False,
        "trading_armed": False,
        "position_close_performed": False,
        "mobile_control_mutation_allowed": False,
        "audit_persistence_enabled": False,
        "replay_persistence_enabled": False,
    }


def _source_metadata() -> dict[str, Any]:
    return {
        "source": "dashboard.runtime.web_kill_switch_governance",
        "read_only": True,
        "projection_only": True,
        "no_mobile_control_import": True,
        "no_broker_calls": True,
        "no_environment_reads": True,
        "no_filesystem_reads": True,
        "no_filesystem_writes": True,
        "no_order_placement": True,
        "no_runtime_authority": True,
        "no_certification_authority": True,
        "frontend_safe": True,
    }


def _action(value: Any) -> str:
    return _safe_text(value).upper().replace("-", "_").replace(" ", "_")


def _operator(value: Any) -> str:
    text = _safe_text(value)
    if not _bounded_identifier(text, max_length=80):
        return ""
    return text


def _reason(value: Any) -> str:
    text = _safe_text(value)
    if len(text) < 6 or len(text) > 240:
        return ""
    if _contains_sensitive_value(text):
        return ""
    return text


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _safe_text(value).upper().replace("-", "_").replace(" ", "_")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bounded_identifier(value: str, *, max_length: int) -> bool:
    if not value or len(value) > max_length:
        return False
    return all(ch.isalnum() or ch in {"-", "_", ".", "@", ":"} for ch in value)


def _contains_sensitive(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                return True
            if _contains_sensitive(item):
                return True
    elif isinstance(value, str):
        return _contains_sensitive_value(value)
    return False


def _contains_sensitive_value(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_VALUE_MARKERS)


def _stable_hash(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "ACTION_ACKNOWLEDGE",
    "ACTION_CANCEL_REQUEST",
    "ACTION_ENGAGE",
    "ACTION_REQUEST_RELEASE",
    "DECISION_APPROVED",
    "DECISION_BLOCKED",
    "DECISION_CANONICAL_UNAVAILABLE",
    "DECISION_INVALID",
    "DECISION_PENDING_CONFIRMATION",
    "DECISION_REJECTED",
    "WEB_KILL_SWITCH_CONFIRMATION_TOKEN",
    "WEB_KILL_SWITCH_GOVERNANCE_VERSION",
    "WEB_KILL_SWITCH_SOURCE_API",
    "WEB_KILL_SWITCH_SOURCE_PAGE",
    "build_kill_switch_audit_preview",
    "build_web_kill_switch_status_payload",
    "engage_web_kill_switch",
    "evaluate_web_kill_switch_governance_request",
]
