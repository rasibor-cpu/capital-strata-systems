"""Canonical Tier-1 broker operational-state framework.

Expected operational conditions are values, not exceptions. Unexpected
software faults are captured as FAILED results at broker boundaries.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, TypeVar

SCHEMA_VERSION = "css.broker.operation_result.v1"


class BrokerOperationalState(str, Enum):
    NOT_INITIALIZED = "NOT_INITIALIZED"
    DISABLED = "DISABLED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    CREDENTIALS_REQUIRED = "CREDENTIALS_REQUIRED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REFRESH_REQUIRED = "TOKEN_REFRESH_REQUIRED"
    ACCOUNT_REQUIRED = "ACCOUNT_REQUIRED"
    ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE"
    ACCOUNT_READY = "ACCOUNT_READY"
    MARKET_DATA_REQUIRED = "MARKET_DATA_REQUIRED"
    MARKET_DATA_UNAVAILABLE = "MARKET_DATA_UNAVAILABLE"
    MARKET_DATA_READY = "MARKET_DATA_READY"
    OPTION_CHAIN_PROVIDER_REQUIRED = "OPTION_CHAIN_PROVIDER_REQUIRED"
    OPTION_CHAIN_UNAVAILABLE = "OPTION_CHAIN_UNAVAILABLE"
    OPTION_CHAIN_READY = "OPTION_CHAIN_READY"
    HOLDINGS_REQUIRED = "HOLDINGS_REQUIRED"
    HOLDINGS_UNAVAILABLE = "HOLDINGS_UNAVAILABLE"
    HOLDINGS_READY = "HOLDINGS_READY"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    DEGRADED = "DEGRADED"
    READ_ONLY_READY = "READ_ONLY_READY"
    ADVISORY_READY = "ADVISORY_READY"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    FAILED = "FAILED"
    # Deprecated source aliases. They resolve to canonical values and are not
    # independent states.
    REGISTERED = "NOT_INITIALIZED"
    UNCONFIGURED = "CONFIGURATION_REQUIRED"
    LIVE_READ_ONLY = "READ_ONLY_READY"
    READY = "READ_ONLY_READY"
    BLOCKED = "EXECUTION_BLOCKED"
    ERROR = "FAILED"


class BrokerCapability(str, Enum):
    ACCOUNT = "ACCOUNT"
    BALANCES = "BALANCES"
    HOLDINGS = "HOLDINGS"
    MARKET_DATA = "MARKET_DATA"
    HISTORICAL_DATA = "HISTORICAL_DATA"
    LISTED_OPTIONS = "LISTED_OPTIONS"
    OPTION_CHAIN = "OPTION_CHAIN"
    FX = "FX"
    CRYPTO = "CRYPTO"
    EQUITIES = "EQUITIES"
    ETFS = "ETFS"
    EXECUTION = "EXECUTION"
    STREAMING = "STREAMING"
    REGISTERED_ACCOUNTS = "REGISTERED_ACCOUNTS"


ALLOWED_TRANSITIONS: Mapping[BrokerOperationalState, frozenset[BrokerOperationalState]] = {
    BrokerOperationalState.NOT_INITIALIZED: frozenset(
        {
            BrokerOperationalState.DISABLED,
            BrokerOperationalState.CONFIGURATION_REQUIRED,
            BrokerOperationalState.CREDENTIALS_REQUIRED,
            BrokerOperationalState.AUTHENTICATION_REQUIRED,
            BrokerOperationalState.FAILED,
        }
    ),
    BrokerOperationalState.CONFIGURATION_REQUIRED: frozenset(
        {BrokerOperationalState.CREDENTIALS_REQUIRED, BrokerOperationalState.AUTHENTICATION_REQUIRED, BrokerOperationalState.DISABLED}
    ),
    BrokerOperationalState.CREDENTIALS_REQUIRED: frozenset(
        {BrokerOperationalState.AUTHENTICATION_REQUIRED, BrokerOperationalState.DISABLED}
    ),
    BrokerOperationalState.AUTHENTICATION_REQUIRED: frozenset(
        {BrokerOperationalState.AUTHENTICATING, BrokerOperationalState.DISABLED}
    ),
    BrokerOperationalState.AUTHENTICATING: frozenset(
        {
            BrokerOperationalState.AUTHENTICATED,
            BrokerOperationalState.AUTHENTICATION_REQUIRED,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
            BrokerOperationalState.RATE_LIMITED,
            BrokerOperationalState.FAILED,
        }
    ),
    BrokerOperationalState.AUTHENTICATED: frozenset(
        {
            BrokerOperationalState.TOKEN_EXPIRED,
            BrokerOperationalState.TOKEN_REFRESH_REQUIRED,
            BrokerOperationalState.ACCOUNT_REQUIRED,
            BrokerOperationalState.ACCOUNT_READY,
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.DEGRADED,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
        }
    ),
    BrokerOperationalState.TOKEN_EXPIRED: frozenset(
        {BrokerOperationalState.TOKEN_REFRESH_REQUIRED, BrokerOperationalState.AUTHENTICATION_REQUIRED}
    ),
    BrokerOperationalState.TOKEN_REFRESH_REQUIRED: frozenset(
        {BrokerOperationalState.AUTHENTICATING, BrokerOperationalState.AUTHENTICATION_REQUIRED}
    ),
    BrokerOperationalState.ACCOUNT_REQUIRED: frozenset(
        {BrokerOperationalState.ACCOUNT_READY, BrokerOperationalState.ACCOUNT_UNAVAILABLE}
    ),
    BrokerOperationalState.ACCOUNT_UNAVAILABLE: frozenset(
        {BrokerOperationalState.ACCOUNT_REQUIRED, BrokerOperationalState.PROVIDER_UNAVAILABLE, BrokerOperationalState.DEGRADED}
    ),
    BrokerOperationalState.ACCOUNT_READY: frozenset(
        {
            BrokerOperationalState.HOLDINGS_READY,
            BrokerOperationalState.MARKET_DATA_READY,
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.DEGRADED,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
        }
    ),
    BrokerOperationalState.MARKET_DATA_REQUIRED: frozenset(
        {
            BrokerOperationalState.MARKET_DATA_READY,
            BrokerOperationalState.MARKET_DATA_UNAVAILABLE,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
        }
    ),
    BrokerOperationalState.MARKET_DATA_UNAVAILABLE: frozenset(
        {
            BrokerOperationalState.MARKET_DATA_REQUIRED,
            BrokerOperationalState.MARKET_DATA_READY,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
            BrokerOperationalState.DEGRADED,
        }
    ),
    BrokerOperationalState.MARKET_DATA_READY: frozenset(
        {
            BrokerOperationalState.MARKET_DATA_REQUIRED,
            BrokerOperationalState.MARKET_DATA_UNAVAILABLE,
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.ADVISORY_READY,
            BrokerOperationalState.DEGRADED,
        }
    ),
    BrokerOperationalState.OPTION_CHAIN_PROVIDER_REQUIRED: frozenset(
        {
            BrokerOperationalState.OPTION_CHAIN_READY,
            BrokerOperationalState.OPTION_CHAIN_UNAVAILABLE,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
        }
    ),
    BrokerOperationalState.OPTION_CHAIN_UNAVAILABLE: frozenset(
        {
            BrokerOperationalState.OPTION_CHAIN_PROVIDER_REQUIRED,
            BrokerOperationalState.OPTION_CHAIN_READY,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
            BrokerOperationalState.DEGRADED,
        }
    ),
    BrokerOperationalState.OPTION_CHAIN_READY: frozenset(
        {
            BrokerOperationalState.OPTION_CHAIN_PROVIDER_REQUIRED,
            BrokerOperationalState.OPTION_CHAIN_UNAVAILABLE,
            BrokerOperationalState.ADVISORY_READY,
            BrokerOperationalState.DEGRADED,
        }
    ),
    BrokerOperationalState.HOLDINGS_REQUIRED: frozenset(
        {
            BrokerOperationalState.HOLDINGS_READY,
            BrokerOperationalState.HOLDINGS_UNAVAILABLE,
            BrokerOperationalState.ACCOUNT_REQUIRED,
        }
    ),
    BrokerOperationalState.HOLDINGS_UNAVAILABLE: frozenset(
        {
            BrokerOperationalState.HOLDINGS_REQUIRED,
            BrokerOperationalState.HOLDINGS_READY,
            BrokerOperationalState.ACCOUNT_UNAVAILABLE,
            BrokerOperationalState.DEGRADED,
        }
    ),
    BrokerOperationalState.HOLDINGS_READY: frozenset(
        {
            BrokerOperationalState.HOLDINGS_REQUIRED,
            BrokerOperationalState.HOLDINGS_UNAVAILABLE,
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.ADVISORY_READY,
            BrokerOperationalState.DEGRADED,
        }
    ),
    BrokerOperationalState.READ_ONLY_READY: frozenset(
        {
            BrokerOperationalState.ADVISORY_READY,
            BrokerOperationalState.TOKEN_REFRESH_REQUIRED,
            BrokerOperationalState.DEGRADED,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
            BrokerOperationalState.RATE_LIMITED,
            BrokerOperationalState.DISABLED,
        }
    ),
    BrokerOperationalState.ADVISORY_READY: frozenset(
        {
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.TOKEN_REFRESH_REQUIRED,
            BrokerOperationalState.MARKET_DATA_UNAVAILABLE,
            BrokerOperationalState.OPTION_CHAIN_UNAVAILABLE,
            BrokerOperationalState.HOLDINGS_UNAVAILABLE,
            BrokerOperationalState.DEGRADED,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
            BrokerOperationalState.RATE_LIMITED,
            BrokerOperationalState.DISABLED,
        }
    ),
    BrokerOperationalState.EXECUTION_BLOCKED: frozenset(
        {
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.ADVISORY_READY,
            BrokerOperationalState.DISABLED,
        }
    ),
    BrokerOperationalState.DEGRADED: frozenset(
        {
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
            BrokerOperationalState.RATE_LIMITED,
            BrokerOperationalState.FAILED,
        }
    ),
    BrokerOperationalState.PROVIDER_UNAVAILABLE: frozenset(
        {BrokerOperationalState.DEGRADED, BrokerOperationalState.READ_ONLY_READY, BrokerOperationalState.FAILED}
    ),
    BrokerOperationalState.RATE_LIMITED: frozenset(
        {BrokerOperationalState.DEGRADED, BrokerOperationalState.READ_ONLY_READY, BrokerOperationalState.PROVIDER_UNAVAILABLE}
    ),
    BrokerOperationalState.DISABLED: frozenset(
        {BrokerOperationalState.NOT_INITIALIZED, BrokerOperationalState.CONFIGURATION_REQUIRED}
    ),
    BrokerOperationalState.FAILED: frozenset(
        {BrokerOperationalState.NOT_INITIALIZED, BrokerOperationalState.DISABLED}
    ),
}

_REDACTED_KEY = re.compile(r"(token|secret|password|authorization|private.?key|api.?key|account.?number)", re.I)
_BEARER = re.compile(r"\bBearer\s+\S+", re.I)
_INLINE_SECRET = re.compile(
    r"\b(token|secret|password|api[_-]?key|authorization|account[_-]?number)\s*[:=]\s*([^\s,;]+)",
    re.I,
)
_T = TypeVar("_T")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): ("[REDACTED]" if _REDACTED_KEY.search(str(key)) else sanitize_value(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_value(item) for item in value]
    if isinstance(value, str):
        text = _BEARER.sub("Bearer [REDACTED]", value)
        return _INLINE_SECRET.sub(r"\1=[REDACTED]", text)[:500]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:500]


@dataclass(frozen=True)
class BrokerOperationResult:
    broker: str
    operation: str
    state: BrokerOperationalState
    success: bool
    retryable: bool
    expected_condition: bool
    failure_code: str | None = None
    operator_message: str = ""
    technical_message: str = ""
    recommended_action: str = ""
    capability: BrokerCapability | None = None
    execution_allowed: bool = False
    advisory_allowed: bool = True
    data: Mapping[str, Any] = field(default_factory=dict)
    provenance: str = "BROKER_OPERATIONAL_STATE"
    provider_timestamp: str | None = None
    received_at: str = ""
    freshness: str = "UNKNOWN"
    latency_ms: float | None = None
    correlation_id: str = ""
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["capability"] = self.capability.value if self.capability else None
        payload["received_at"] = self.received_at or utc_now()
        payload["data"] = sanitize_value(self.data)
        payload["operator_message"] = str(sanitize_value(self.operator_message))
        payload["technical_message"] = str(sanitize_value(self.technical_message))
        payload["recommended_action"] = str(sanitize_value(self.recommended_action))
        payload["execution_allowed"] = False
        payload["state_hash"] = _state_hash(payload)
        return payload


def operation_result(
    *,
    broker: str,
    operation: str,
    state: BrokerOperationalState | str,
    success: bool | None = None,
    retryable: bool = False,
    expected_condition: bool = True,
    failure_code: str | None = None,
    operator_message: str = "",
    technical_message: str = "",
    recommended_action: str = "",
    capability: BrokerCapability | str | None = None,
    data: Mapping[str, Any] | None = None,
    provider_timestamp: str | None = None,
    freshness: str = "UNKNOWN",
    latency_ms: float | None = None,
    correlation_id: str | None = None,
    provenance: str = "BROKER_OPERATIONAL_STATE",
) -> BrokerOperationResult:
    normalized_state = state if isinstance(state, BrokerOperationalState) else BrokerOperationalState(str(state).upper())
    normalized_capability = (
        capability
        if isinstance(capability, BrokerCapability)
        else BrokerCapability(str(capability).upper())
        if capability
        else None
    )
    if success is None:
        success = normalized_state in {
            BrokerOperationalState.AUTHENTICATED,
            BrokerOperationalState.ACCOUNT_READY,
            BrokerOperationalState.MARKET_DATA_READY,
            BrokerOperationalState.OPTION_CHAIN_READY,
            BrokerOperationalState.HOLDINGS_READY,
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.ADVISORY_READY,
        }
    return BrokerOperationResult(
        broker=str(broker or "NONE").upper(),
        operation=str(operation or "status").lower(),
        state=normalized_state,
        success=bool(success),
        retryable=bool(retryable),
        expected_condition=bool(expected_condition),
        failure_code=failure_code,
        operator_message=operator_message,
        technical_message=technical_message,
        recommended_action=recommended_action,
        capability=normalized_capability,
        execution_allowed=False,
        advisory_allowed=True,
        data=sanitize_value(dict(data or {})),
        provenance=provenance,
        provider_timestamp=provider_timestamp,
        received_at=utc_now(),
        freshness=str(freshness or "UNKNOWN").upper(),
        latency_ms=latency_ms,
        correlation_id=correlation_id or uuid.uuid4().hex,
    )


def validate_transition(
    current: BrokerOperationalState | str,
    target: BrokerOperationalState | str,
) -> BrokerOperationResult:
    source = current if isinstance(current, BrokerOperationalState) else BrokerOperationalState(str(current).upper())
    destination = target if isinstance(target, BrokerOperationalState) else BrokerOperationalState(str(target).upper())
    allowed = destination == source or destination in ALLOWED_TRANSITIONS.get(source, frozenset())
    return operation_result(
        broker="SYSTEM",
        operation="validate_transition",
        state=destination if allowed else BrokerOperationalState.FAILED,
        success=allowed,
        expected_condition=allowed,
        failure_code=None if allowed else "INVALID_STATE_TRANSITION",
        operator_message="Transition accepted" if allowed else "Broker state transition rejected",
        technical_message=f"{source.value}->{destination.value}",
        recommended_action="" if allowed else "Review canonical broker transition rules",
        data={"from_state": source.value, "to_state": destination.value, "valid": allowed},
    )


def capture_unexpected_fault(
    broker: str,
    operation: str,
    func: Callable[[], _T],
    *,
    capability: BrokerCapability | None = None,
) -> _T | BrokerOperationResult:
    try:
        return func()
    except Exception as exc:  # noqa: BLE001 - boundary for genuine unexpected faults
        correlation_id = uuid.uuid4().hex
        return operation_result(
            broker=broker,
            operation=operation,
            state=BrokerOperationalState.FAILED,
            success=False,
            retryable=False,
            expected_condition=False,
            failure_code="UNEXPECTED_SOFTWARE_FAULT",
            operator_message="Broker operation failed unexpectedly",
            technical_message=f"{type(exc).__name__}: {exc}",
            recommended_action=f"Inspect sanitized diagnostics using correlation ID {correlation_id}",
            capability=capability,
            correlation_id=correlation_id,
        )


def state_definitions() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "states": [state.value for state in BrokerOperationalState],
        "capabilities": [capability.value for capability in BrokerCapability],
        "transitions": {
            source.value: sorted(target.value for target in targets)
            for source, targets in ALLOWED_TRANSITIONS.items()
        },
        "execution_states_available": False,
        "execution_allowed": False,
    }


def certification_outcome(state: BrokerOperationalState | str) -> str:
    normalized = state if isinstance(state, BrokerOperationalState) else BrokerOperationalState(str(state).upper())
    if normalized in {
        BrokerOperationalState.CONFIGURATION_REQUIRED,
        BrokerOperationalState.CREDENTIALS_REQUIRED,
        BrokerOperationalState.AUTHENTICATION_REQUIRED,
        BrokerOperationalState.NOT_INITIALIZED,
        BrokerOperationalState.DISABLED,
    }:
        return "NOT_INITIALIZED"
    if normalized in {
        BrokerOperationalState.AUTHENTICATING,
        BrokerOperationalState.AUTHENTICATED,
        BrokerOperationalState.ACCOUNT_REQUIRED,
        BrokerOperationalState.ACCOUNT_READY,
        BrokerOperationalState.MARKET_DATA_REQUIRED,
    }:
        return "CONFIGURED"
    if normalized in {
        BrokerOperationalState.READ_ONLY_READY,
        BrokerOperationalState.ADVISORY_READY,
        BrokerOperationalState.MARKET_DATA_READY,
        BrokerOperationalState.HOLDINGS_READY,
        BrokerOperationalState.OPTION_CHAIN_READY,
    }:
        return "READ_ONLY_READY"
    if normalized is BrokerOperationalState.FAILED:
        return "FAILED"
    return "NOT_INITIALIZED"


def _state_hash(payload: Mapping[str, Any]) -> str:
    body = {
        key: value
        for key, value in payload.items()
        if key not in {"state_hash", "correlation_id", "received_at"}
    }
    canonical = json.dumps(sanitize_value(body), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "ALLOWED_TRANSITIONS",
    "BrokerCapability",
    "BrokerOperationalState",
    "BrokerOperationResult",
    "SCHEMA_VERSION",
    "capture_unexpected_fault",
    "certification_outcome",
    "operation_result",
    "sanitize_value",
    "state_definitions",
    "utc_now",
    "validate_transition",
]
