from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from math import isfinite
from typing import Any, Mapping


SCHEMA_VERSION = "css.phase166b.canonical_broker_runtime_state.v1"

STATUS_PASS = "PASS"
STATUS_WARNING = "WARNING"
STATUS_FAIL = "FAIL"
STATUS_NOT_TESTED = "NOT_TESTED"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_BLOCKED = "BLOCKED"
STATUS_UNKNOWN = "UNKNOWN"

OVERALL_GREEN = "GREEN"
OVERALL_AMBER = "AMBER"
OVERALL_RED = "RED"
OVERALL_UNAVAILABLE = "UNAVAILABLE"
OVERALL_CONTRADICTORY = "CONTRADICTORY"
OVERALL_FAIL_CLOSED = "FAIL_CLOSED"

CANONICAL_STATUSES = frozenset(
    {
        STATUS_PASS,
        STATUS_WARNING,
        STATUS_FAIL,
        STATUS_NOT_TESTED,
        STATUS_UNAVAILABLE,
        STATUS_BLOCKED,
        STATUS_UNKNOWN,
    }
)

OVERALL_STATUSES = frozenset(
    {
        OVERALL_GREEN,
        OVERALL_AMBER,
        OVERALL_RED,
        OVERALL_UNAVAILABLE,
        OVERALL_CONTRADICTORY,
        OVERALL_FAIL_CLOSED,
    }
)

_READY_VALUES = frozenset({"PASS", "PRESENT", "READY", "OK", "AVAILABLE", "AUTHENTICATED", "CONNECTED", "GREEN", "OPERATIONAL"})
_FAIL_VALUES = frozenset({"FAIL", "FAILED", "ERROR", "RED", "NOT_AUTHENTICATED", "AUTH_FAILED", "MISSING"})
_BLOCK_VALUES = frozenset({"BLOCKED", "DISABLED", "NO_GO", "NO GO", "REJECTED"})


@dataclass(frozen=True)
class CanonicalBrokerRuntimeState:
    broker: str = "NONE"
    mode: str = "paper"
    credential_status: str = STATUS_UNKNOWN
    authentication_status: str = STATUS_NOT_TESTED
    connection_status: str = STATUS_UNKNOWN
    account_status: str = STATUS_UNAVAILABLE
    balance_status: str = STATUS_UNAVAILABLE
    buying_power_status: str = STATUS_UNAVAILABLE
    margin_status: str = STATUS_UNAVAILABLE
    market_data_status: str = STATUS_NOT_TESTED
    product_status: str = STATUS_NOT_TESTED
    order_submission_status: str = STATUS_BLOCKED
    execution_scope: str = "READ_ONLY"
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    operator_intent: str = "NONE"
    pilot_state: str = "DISARMED"
    capital_governor: str = "PHASE_152A_CAD20_GUARD_ONLY"
    readiness_state: str = "UNCONFIGURED"
    readiness_score: float = 0.0
    overall_status: str = OVERALL_UNAVAILABLE
    last_successful_auth: str = ""
    last_successful_account_read: str = ""
    last_successful_balance_read: str = ""
    last_successful_market_data: str = ""
    latency_ms: int | None = None
    http_status: int | None = None
    error_code: str = ""
    failure_reason: str = ""
    warning_reasons: tuple[str, ...] = ()
    environment_evidence: Mapping[str, Any] = field(default_factory=dict)
    account_evidence: Mapping[str, Any] = field(default_factory=dict)
    source_modules: tuple[str, ...] = ()
    timestamp: str = ""
    schema_version: str = SCHEMA_VERSION
    contradiction_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "broker", str(self.broker or "NONE").upper())
        object.__setattr__(self, "mode", str(self.mode or "paper").lower())
        for name in (
            "credential_status",
            "authentication_status",
            "connection_status",
            "account_status",
            "balance_status",
            "buying_power_status",
            "margin_status",
            "market_data_status",
            "product_status",
            "order_submission_status",
        ):
            object.__setattr__(self, name, canonical_status(getattr(self, name)))
        object.__setattr__(self, "overall_status", canonical_overall(self.overall_status))
        object.__setattr__(self, "execution_allowed", bool(self.execution_allowed) and not bool(self.live_trading_blocked) and bool(self.broker_execution_armed))
        object.__setattr__(self, "live_trading_blocked", True)
        object.__setattr__(self, "broker_execution_armed", False)
        object.__setattr__(self, "readiness_score", finite_float(self.readiness_score, default=0.0))
        if self.latency_ms is not None:
            object.__setattr__(self, "latency_ms", finite_int(self.latency_ms))
        if self.http_status is not None:
            object.__setattr__(self, "http_status", finite_int(self.http_status))
        object.__setattr__(self, "warning_reasons", tuple(str(item) for item in self.warning_reasons if str(item)))
        object.__setattr__(self, "source_modules", tuple(dict.fromkeys(str(item) for item in self.source_modules if str(item))))
        object.__setattr__(self, "contradiction_reasons", tuple(str(item) for item in self.contradiction_reasons if str(item)))

    @property
    def is_fail_closed(self) -> bool:
        return (
            self.execution_allowed is False
            and self.live_trading_blocked is True
            and self.broker_execution_armed is False
            and self.overall_status in {OVERALL_RED, OVERALL_UNAVAILABLE, OVERALL_CONTRADICTORY, OVERALL_FAIL_CLOSED}
        )

    def with_fail_closed(self, reasons: list[str] | tuple[str, ...], *, contradictory: bool = False) -> "CanonicalBrokerRuntimeState":
        current = list(self.contradiction_reasons)
        current.extend(str(item) for item in reasons if str(item))
        return replace(
            self,
            execution_allowed=False,
            live_trading_blocked=True,
            broker_execution_armed=False,
            overall_status=OVERALL_CONTRADICTORY if contradictory else OVERALL_FAIL_CLOSED,
            contradiction_reasons=tuple(dict.fromkeys(current)),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["environment_evidence"] = json_safe(dict(self.environment_evidence))
        payload["account_evidence"] = json_safe(dict(self.account_evidence))
        payload["warning_reasons"] = list(self.warning_reasons)
        payload["source_modules"] = list(self.source_modules)
        payload["contradiction_reasons"] = list(self.contradiction_reasons)
        payload["state_hash"] = self.stable_hash()
        return json_safe(payload)

    def stable_json(self) -> str:
        payload = asdict(self)
        payload["environment_evidence"] = json_safe(dict(self.environment_evidence))
        payload["account_evidence"] = json_safe(dict(self.account_evidence))
        return json.dumps(json_safe(payload), sort_keys=True, separators=(",", ":"), default=str)

    def stable_hash(self) -> str:
        return hashlib.sha256(self.stable_json().encode("utf-8")).hexdigest()


def canonical_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in CANONICAL_STATUSES:
        return text
    if text in _READY_VALUES:
        return STATUS_PASS
    if text in _FAIL_VALUES:
        return STATUS_FAIL
    if text in _BLOCK_VALUES:
        return STATUS_BLOCKED
    if text in {"PENDING", ""}:
        return STATUS_NOT_TESTED if not text else STATUS_UNKNOWN
    if text in {"NOT_AVAILABLE", "DATA UNAVAILABLE", "UNAVAILABLE"}:
        return STATUS_UNAVAILABLE
    return STATUS_UNKNOWN


def canonical_overall(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in OVERALL_STATUSES:
        return text
    if text in _READY_VALUES:
        return OVERALL_GREEN
    if text in {"WARN", "WARNING", "DEGRADED", "AMBER"}:
        return OVERALL_AMBER
    if text in _FAIL_VALUES:
        return OVERALL_RED
    if text in _BLOCK_VALUES:
        return OVERALL_FAIL_CLOSED
    return OVERALL_UNAVAILABLE


def finite_float(value: Any, *, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def finite_int(value: Any) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return int(round(number))


def json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "CANONICAL_STATUSES",
    "OVERALL_STATUSES",
    "OVERALL_AMBER",
    "OVERALL_CONTRADICTORY",
    "OVERALL_FAIL_CLOSED",
    "OVERALL_GREEN",
    "OVERALL_RED",
    "OVERALL_UNAVAILABLE",
    "SCHEMA_VERSION",
    "STATUS_BLOCKED",
    "STATUS_FAIL",
    "STATUS_NOT_TESTED",
    "STATUS_PASS",
    "STATUS_UNAVAILABLE",
    "STATUS_UNKNOWN",
    "STATUS_WARNING",
    "CanonicalBrokerRuntimeState",
    "canonical_overall",
    "canonical_status",
]
