from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class TradeState(str, Enum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRE_USER_AUTH = "REQUIRE_USER_AUTH"
    SIMULATED = "SIMULATED"
    CLOSED = "CLOSED"
    LOGGED = "LOGGED"


class TradeLifecycleStage(str, Enum):
    SIGNAL_RECEIVED = "SIGNAL_RECEIVED"
    GOVERNANCE_CHECKED = "GOVERNANCE_CHECKED"
    RISK_CHECKED = "RISK_CHECKED"
    BROKER_ROUTE_SELECTED = "BROKER_ROUTE_SELECTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    EXECUTION_REPORTED = "EXECUTION_REPORTED"
    LEDGER_POSTED = "LEDGER_POSTED"
    DASHBOARD_PUBLISHED = "DASHBOARD_PUBLISHED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TradeLifecycle:
    """
    Minimal state container for trade lifecycle control.
    Transitions will be implemented in later steps.
    """
    trade_id: str
    state: TradeState
    created_ts: float
    updated_ts: float
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class TradeLifecycleAuditEvent:
    """
    Frontend-safe audit event for one stage of a trade lifecycle.
    """

    trade_id: str
    stage: TradeLifecycleStage
    timestamp_utc: str
    symbol: str = ""
    asset_class: str = ""
    side: str = ""
    mode: str = "paper"
    status: str = "RECORDED"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "stage": self.stage.value,
            "timestamp_utc": self.timestamp_utc,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "side": self.side,
            "mode": self.mode,
            "status": self.status,
            "reason": self.reason,
            "metadata": _redact(self.metadata),
        }


class TradeLifecycleAuditTrail:
    """
    In-memory audit trail builder for deterministic PCNRASS validation.

    Persistence and UI viewing are handled in later phases; this class only
    standardizes the event shape and redaction boundary.
    """

    def __init__(self, trade_id: str) -> None:
        self.trade_id = str(trade_id)
        self._events: list[TradeLifecycleAuditEvent] = []

    def record(
        self,
        stage: TradeLifecycleStage | str,
        *,
        symbol: str = "",
        asset_class: str = "",
        side: str = "",
        mode: str = "paper",
        status: str = "RECORDED",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TradeLifecycleAuditEvent:
        event = TradeLifecycleAuditEvent(
            trade_id=self.trade_id,
            stage=_stage(stage),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            symbol=str(symbol),
            asset_class=str(asset_class).upper(),
            side=str(side).upper(),
            mode=_mode(mode),
            status=str(status),
            reason=str(reason),
            metadata=dict(metadata or {}),
        )
        self._events.append(event)
        return event

    def events(self) -> tuple[TradeLifecycleAuditEvent, ...]:
        return tuple(self._events)

    def stages(self) -> tuple[str, ...]:
        return tuple(event.stage.value for event in self._events)

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "event_count": len(self._events),
            "stages": list(self.stages()),
            "events": [event.as_dict() for event in self._events],
        }


def build_trade_lifecycle_audit(
    *,
    trade_id: str,
    symbol: str,
    asset_class: str,
    side: str,
    mode: str = "paper",
    accepted: bool = True,
    reason: str = "",
) -> TradeLifecycleAuditTrail:
    trail = TradeLifecycleAuditTrail(trade_id)
    common = {
        "symbol": symbol,
        "asset_class": asset_class,
        "side": side,
        "mode": mode,
    }
    trail.record(TradeLifecycleStage.SIGNAL_RECEIVED, **common)
    trail.record(TradeLifecycleStage.GOVERNANCE_CHECKED, **common)
    trail.record(TradeLifecycleStage.RISK_CHECKED, **common)

    if not accepted:
        trail.record(
            TradeLifecycleStage.BLOCKED,
            **common,
            status="BLOCKED",
            reason=reason or "trade_blocked",
        )
        return trail

    trail.record(TradeLifecycleStage.BROKER_ROUTE_SELECTED, **common)
    trail.record(TradeLifecycleStage.ORDER_SUBMITTED, **common)
    trail.record(TradeLifecycleStage.EXECUTION_REPORTED, **common)
    trail.record(TradeLifecycleStage.LEDGER_POSTED, **common)
    trail.record(TradeLifecycleStage.DASHBOARD_PUBLISHED, **common)
    return trail


def _stage(value: TradeLifecycleStage | str) -> TradeLifecycleStage:
    if isinstance(value, TradeLifecycleStage):
        return value

    return TradeLifecycleStage(str(value).strip().upper())


def _mode(value: str) -> str:
    normalized = str(value).strip().lower()
    return "live" if normalized == "live" else "paper"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "REDACTED"
                if _is_sensitive_key(str(key))
                else _redact(item)
            )
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_redact(item) for item in value]

    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    sensitive_fragments = (
        "api_key",
        "access_key",
        "private_key",
        "secret",
        "token",
        "password",
        "passphrase",
        "credential",
        "authorization",
        "bearer",
    )
    return normalized == "key" or any(
        fragment in normalized for fragment in sensitive_fragments
    )
