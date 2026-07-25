from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.governance.enterprise_execution_gateway import SCHEMA_VERSION as PPF003_SCHEMA_VERSION
from backend.governance.enterprise_exposure_registry import SCHEMA_VERSION as PPF002_SCHEMA_VERSION
from backend.governance.enterprise_profit_protection_contracts import SCHEMA_VERSION as PPF001_SCHEMA_VERSION
from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


SCHEMA_VERSION = "css.ppf006.enterprise_profit_protection.mission_control_projection.v1"
PPF004_SCHEMA_VERSION = "css.ppf004.canonical_execution_advisory.v1"

REASON_ADVISORY_ONLY = "ADVISORY_ONLY"
REASON_READ_ONLY_PROJECTION = "READ_ONLY_PROJECTION"
REASON_PPF_EVIDENCE_PROJECTED = "PPF_EVIDENCE_PROJECTED"
REASON_MISSING_PPF_GOVERNANCE_EVIDENCE = "MISSING_PPF_GOVERNANCE_EVIDENCE"
REASON_MISSING_PPF_DECISION = "MISSING_PPF_DECISION"
REASON_MISSING_EXPOSURE_STATE = "MISSING_EXPOSURE_STATE"
REASON_MISSING_OBSERVED_AT = "MISSING_OBSERVED_AT"
REASON_DATA_STALE = "DATA_STALE"
REASON_INVALID_PPF_EVIDENCE = "INVALID_PPF_EVIDENCE"
REASON_SOURCE_FAIL_CLOSED = "SOURCE_FAIL_CLOSED"
REASON_SOURCE_EXECUTION_AUTHORITY_IGNORED = "SOURCE_EXECUTION_AUTHORITY_IGNORED"
REASON_OK = "OK"


def build_profit_protection_governance_projection(
    evidence: Mapping[str, Any] | None,
    *,
    generated_at: str = DATA_UNAVAILABLE,
    runtime_source: str = DATA_UNAVAILABLE,
    runtime_state_hash: str = DATA_UNAVAILABLE,
    now: datetime | None = None,
    max_age_seconds: int = 300,
) -> dict[str, Any]:
    source = _mapping(evidence)
    observed_at = _text(source.get("observed_at") or source.get("generated_at"))
    current = now or datetime.now(timezone.utc)
    freshness = _freshness(observed_at, current, max_age_seconds=max_age_seconds)

    gateway_decision = _mapping(source.get("gateway_decision"))
    gateway_state = _mapping(gateway_decision.get("state"))
    ppf_decision = (
        _mapping(gateway_decision.get("ppf_decision"))
        or _mapping(gateway_state.get("ppf_decision"))
        or _mapping(source.get("ppf_decision"))
    )
    registry_result = _mapping(gateway_decision.get("registry_result"))
    exposure_state = (
        _mapping(gateway_state.get("exposure_state"))
        or _mapping(registry_result.get("state"))
        or _mapping(source.get("exposure_state"))
    )
    ppf_state = _mapping(ppf_decision.get("state"))

    reasons: list[str] = [REASON_ADVISORY_ONLY, REASON_READ_ONLY_PROJECTION]
    if not source:
        reasons.append(REASON_MISSING_PPF_GOVERNANCE_EVIDENCE)
    if not ppf_decision:
        reasons.append(REASON_MISSING_PPF_DECISION)
    if not exposure_state:
        reasons.append(REASON_MISSING_EXPOSURE_STATE)
    if not observed_at:
        reasons.append(REASON_MISSING_OBSERVED_AT)
    if freshness["freshness_status"] == "STALE":
        reasons.append(REASON_DATA_STALE)
    if str(source.get("status", "")).upper() == "FAIL_CLOSED":
        reasons.append(REASON_SOURCE_FAIL_CLOSED)
    if _truthy_execution_allowed(source, gateway_decision, ppf_decision, exposure_state):
        reasons.append(REASON_SOURCE_EXECUTION_AUTHORITY_IGNORED)

    money_fields = {
        "approved_banked_net_profit": _value(ppf_state, ppf_decision, "banked_net_profit"),
        "effective_protection_ceiling": _value(ppf_decision, ppf_state, "effective_ceiling"),
        "base_protection_budget": _value(ppf_decision, ppf_state, "base_budget"),
        "adjusted_protection_budget": _value(ppf_decision, ppf_state, "adjusted_budget"),
        "committed_exposure": exposure_state.get("current_enterprise_exposure"),
        "reserved_exposure": exposure_state.get("reserved_exposure"),
        "remaining_exposure_capacity": exposure_state.get("remaining_enterprise_risk_budget"),
    }
    invalid_money = _invalid_money(money_fields)
    if invalid_money:
        reasons.append(REASON_INVALID_PPF_EVIDENCE)

    source_stale = bool(gateway_state.get("stale")) or bool(exposure_state.get("stale"))
    if source_stale:
        reasons.append(REASON_DATA_STALE)

    fail_closed = any(
        reason
        in {
            REASON_MISSING_PPF_GOVERNANCE_EVIDENCE,
            REASON_MISSING_PPF_DECISION,
            REASON_MISSING_EXPOSURE_STATE,
            REASON_MISSING_OBSERVED_AT,
            REASON_DATA_STALE,
            REASON_INVALID_PPF_EVIDENCE,
            REASON_SOURCE_FAIL_CLOSED,
            REASON_SOURCE_EXECUTION_AUTHORITY_IGNORED,
        }
        for reason in reasons
    )
    if not fail_closed:
        reasons.extend([REASON_PPF_EVIDENCE_PROJECTED, REASON_OK])

    enforcement_status = str(ppf_decision.get("enforcement_status") or source.get("status") or "FAIL_CLOSED")
    status = "FAIL_CLOSED" if fail_closed else enforcement_status
    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(source.get("schema_version") or DATA_UNAVAILABLE),
        "source_schema_versions": {
            "ppf001": PPF001_SCHEMA_VERSION,
            "ppf002": PPF002_SCHEMA_VERSION,
            "ppf003": PPF003_SCHEMA_VERSION,
            "ppf004": str(source.get("schema_version") or PPF004_SCHEMA_VERSION),
        },
        "status": status,
        "gateway_status": str(source.get("status") or DATA_UNAVAILABLE),
        "current_enforcement_status": enforcement_status,
        "enforcement_status": enforcement_status,
        "posture": str(ppf_decision.get("posture") or ppf_state.get("posture") or "FAIL_CLOSED"),
        "maturity_tier": str(ppf_decision.get("maturity_tier") or ppf_state.get("maturity_tier") or DATA_UNAVAILABLE),
        "approved_banked_net_profit": _money_text(money_fields["approved_banked_net_profit"], allow_negative=True),
        "effective_protection_ceiling": _money_text(money_fields["effective_protection_ceiling"]),
        "base_protection_budget": _money_text(money_fields["base_protection_budget"]),
        "adjusted_protection_budget": _money_text(money_fields["adjusted_protection_budget"]),
        "committed_exposure": _money_text(money_fields["committed_exposure"]),
        "reserved_exposure": _money_text(money_fields["reserved_exposure"]),
        "remaining_exposure_capacity": (
            "0.00" if fail_closed else _money_text(money_fields["remaining_exposure_capacity"])
        ),
        "active_reservation_count": exposure_state.get("active_reservation_count", 0 if fail_closed else DATA_UNAVAILABLE),
        "reservation_count": exposure_state.get("reservation_count", 0 if fail_closed else DATA_UNAVAILABLE),
        "module_attribution": dict(exposure_state.get("module_attribution") or {}),
        "reservation_id": source.get("reservation_id"),
        "requested_exposure": source.get("requested_exposure"),
        "reason_codes": _dedupe(reasons),
        "upstream_reason_codes": _dedupe_str(
            [
                *_strings(source.get("upstream_reason_codes")),
                *_strings(ppf_decision.get("reason_codes")),
                *_strings(exposure_state.get("reason_codes")),
            ]
        ),
        "data_freshness": freshness,
        "observed_at": observed_at or DATA_UNAVAILABLE,
        "generated_at": generated_at,
        "source": _source(source, runtime_source),
        "source_module": "dashboard.mission_control.profit_protection_projection",
        "state_hash": runtime_state_hash,
        "fail_closed": fail_closed,
        "read_only": True,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "policy_change_allowed": False,
        "automatic_policy_increase_allowed": False,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _value(primary: Mapping[str, Any], fallback: Mapping[str, Any], key: str) -> Any:
    return primary.get(key, fallback.get(key))


def _money_text(value: Any, *, allow_negative: bool = False) -> str:
    converted = _decimal(value)
    if converted is None or (converted < Decimal("0") and not allow_negative):
        return DATA_UNAVAILABLE
    return format(converted, "f")


def _invalid_money(fields: Mapping[str, Any]) -> bool:
    for key, value in fields.items():
        converted = _decimal(value)
        if converted is None:
            return True
        if key != "approved_banked_net_profit" and converted < Decimal("0"):
            return True
    return False


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", DATA_UNAVAILABLE):
        return None
    text = repr(value) if isinstance(value, float) else str(value)
    try:
        converted = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not converted.is_finite():
        return None
    return converted


def _freshness(observed_at: str, now: datetime, *, max_age_seconds: int) -> dict[str, Any]:
    if not observed_at:
        return {
            "freshness_status": "UNAVAILABLE",
            "observed_at": DATA_UNAVAILABLE,
            "age_seconds": DATA_UNAVAILABLE,
            "stale": True,
        }
    parsed = _parse_time(observed_at)
    if parsed is None:
        return {
            "freshness_status": "UNAVAILABLE",
            "observed_at": observed_at,
            "age_seconds": DATA_UNAVAILABLE,
            "stale": True,
        }
    age = round(max((now.astimezone(timezone.utc) - parsed).total_seconds(), 0.0), 3)
    stale = age > max_age_seconds
    return {
        "freshness_status": "STALE" if stale else "FRESH",
        "observed_at": observed_at,
        "age_seconds": age,
        "stale": stale,
    }


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source(source: Mapping[str, Any], runtime_source: str) -> str:
    explicit = str(source.get("source") or source.get("data_source") or "").upper().strip()
    if explicit:
        return explicit
    return str(runtime_source or DATA_UNAVAILABLE)


def _truthy_execution_allowed(*payloads: Mapping[str, Any]) -> bool:
    return any(payload.get("execution_allowed") is True for payload in payloads if payload)


def _strings(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


def _dedupe(reasons: list[str]) -> list[str]:
    result: list[str] = []
    for reason in reasons:
        if reason not in result:
            result.append(reason)
    return result


def _dedupe_str(reasons: list[str]) -> list[str]:
    return _dedupe([str(reason) for reason in reasons])


__all__ = [
    "SCHEMA_VERSION",
    "build_profit_protection_governance_projection",
]
