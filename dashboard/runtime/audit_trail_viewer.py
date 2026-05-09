from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AUDIT_PAYLOAD_VERSION = "css.audit.viewer.v1"
AUDIT_CATEGORY_OPTIONS = (
    "approval",
    "broker_disconnect",
    "execution_attempt",
    "governance_block",
    "kill_switch",
    "live_paper_transition",
    "login",
    "mode_change",
    "permission_denial",
    "rejection",
)
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "private",
    "pem",
)


@dataclass(frozen=True)
class AuditTrailEvent:
    event_id: str
    timestamp_utc: str
    category: str
    action: str
    actor: str
    status: str
    source: str
    reason: str
    replayable: bool
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc,
            "category": self.category,
            "action": self.action,
            "actor": self.actor,
            "status": self.status,
            "source": self.source,
            "reason": self.reason,
            "replayable": self.replayable,
            "payload": _redact(self.payload),
        }


def load_mobile_trade_audit_events(
    path: str | Path,
    *,
    limit: int = 100,
) -> tuple[AuditTrailEvent, ...]:
    source_path = Path(path)
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ()
    except Exception:
        return ()

    events: list[AuditTrailEvent] = []
    for line in reversed(lines):
        try:
            raw = json.loads(line)
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        events.append(mobile_trade_event_to_audit_event(raw))
        if len(events) >= limit:
            break
    return tuple(events)


def mobile_trade_event_to_audit_event(raw: Mapping[str, Any]) -> AuditTrailEvent:
    ticket = _mapping(raw.get("ticket"))
    status = str(raw.get("status", "UNKNOWN") or "UNKNOWN")
    category = _category_for_status(status, raw)
    timestamp = str(
        raw.get("recorded_utc")
        or ticket.get("created_utc")
        or datetime.now(timezone.utc).isoformat()
    )
    event_id = str(
        raw.get("event_id")
        or ticket.get("ticket_id")
        or _stable_hash(raw)
    )
    source = str(ticket.get("source") or raw.get("source") or "CSS_MOBILE")
    actor = str(
        ticket.get("user_id")
        or raw.get("user_id")
        or raw.get("actor")
        or "UNKNOWN"
    )
    return AuditTrailEvent(
        event_id=event_id,
        timestamp_utc=timestamp,
        category=category,
        action=status,
        actor=actor,
        status=status,
        source=source,
        reason=_reason_for_event(status, raw),
        replayable=bool(ticket),
        payload=_redact(raw),
    )


def filter_audit_events(
    events: Iterable[AuditTrailEvent],
    *,
    category: str = "",
    status: str = "",
    actor: str = "",
) -> tuple[AuditTrailEvent, ...]:
    category_filter = category.strip().lower()
    status_filter = status.strip().lower()
    actor_filter = actor.strip().lower()
    filtered: list[AuditTrailEvent] = []

    for event in events:
        if category_filter and event.category.lower() != category_filter:
            continue
        if status_filter and status_filter not in event.status.lower():
            continue
        if actor_filter and actor_filter not in event.actor.lower():
            continue
        filtered.append(event)
    return tuple(filtered)


def summarize_audit_events(events: Sequence[AuditTrailEvent]) -> dict[str, Any]:
    categories: dict[str, int] = {}
    replayable = 0
    for event in events:
        categories[event.category] = categories.get(event.category, 0) + 1
        replayable += 1 if event.replayable else 0
    return {
        "event_count": len(events),
        "category_counts": categories,
        "replayable_count": replayable,
    }


def export_audit_events(events: Sequence[AuditTrailEvent]) -> dict[str, Any]:
    summary = summarize_audit_events(events)
    payload = {
        "payload_version": AUDIT_PAYLOAD_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "DashboardState-compatible audit viewer",
        **summary,
        "events": [event.as_dict() for event in events],
    }
    return _redact(payload)


def _category_for_status(status: str, raw: Mapping[str, Any]) -> str:
    explicit = str(raw.get("category", "") or "").strip().lower()
    if explicit in AUDIT_CATEGORY_OPTIONS:
        return explicit

    normalized = status.strip().upper()
    if normalized == "PAPER_TICKET_RECORDED" or normalized.endswith("_ORDER_SENT"):
        return "approval"
    if normalized == "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED":
        return "kill_switch"
    if normalized == "MOBILE_AUTHORITY_DENIED":
        return "permission_denial"
    if normalized in {"MOBILE_ORDERS_DISABLED", "LIVE_CONFIRMATION_REQUIRED"}:
        return "governance_block"
    if "MODE" in normalized and ("LIVE" in normalized or "PAPER" in normalized):
        return "live_paper_transition"
    if "DISCONNECT" in normalized:
        return "broker_disconnect"
    if any(marker in normalized for marker in ("FAILED", "BLOCKED", "NOT_CONFIGURED", "NOT_SUPPORTED", "REQUIRES")):
        return "rejection"
    return "execution_attempt"


def _reason_for_event(status: str, raw: Mapping[str, Any]) -> str:
    broker_response = _mapping(raw.get("broker_response"))
    for key in (
        "kill_switch_reason",
        "required_control",
        "required_confirmation",
        "error",
        "message",
        "required",
    ):
        value = broker_response.get(key)
        if value not in (None, ""):
            return str(value)
    return status


def _stable_hash(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(_redact(value), sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16].upper()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(key)
            if _is_sensitive_key(safe_key):
                redacted[safe_key] = "REDACTED"
            else:
                redacted[safe_key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)
