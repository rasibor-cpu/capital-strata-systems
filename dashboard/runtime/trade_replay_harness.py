from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.audit_trail_viewer import (
    AuditTrailEvent,
    load_mobile_trade_audit_events,
)


TRADE_REPLAY_PAYLOAD_VERSION = "css.trade_replay.v1"
ACCEPTED_LIFECYCLE_PATH = (
    "SIGNAL_RECEIVED",
    "GOVERNANCE_CHECKED",
    "RISK_CHECKED",
    "BROKER_ROUTE_SELECTED",
    "ORDER_SUBMITTED",
    "EXECUTION_REPORTED",
    "LEDGER_POSTED",
    "DASHBOARD_PUBLISHED",
)
BLOCKED_LIFECYCLE_PATH = (
    "SIGNAL_RECEIVED",
    "GOVERNANCE_CHECKED",
    "RISK_CHECKED",
    "BLOCKED",
)
REJECTED_LIFECYCLE_PATH = (
    "SIGNAL_RECEIVED",
    "GOVERNANCE_CHECKED",
    "RISK_CHECKED",
    "REJECTED",
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
    "authorization",
    "bearer",
)


@dataclass(frozen=True)
class TradeReplayStep:
    sequence: int
    step_id: str
    timestamp_utc: str
    category: str
    expected_action: str
    actual_action: str
    expected_status: str
    actual_status: str
    actor: str = ""
    source: str = ""
    mode: str = "paper"
    reason: str = ""
    duration_since_previous_ms: float | None = None
    payload: dict[str, Any] | None = None

    @property
    def matched(self) -> bool:
        return (
            self.expected_action == self.actual_action
            and self.expected_status == self.actual_status
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "step_id": self.step_id,
            "timestamp_utc": self.timestamp_utc,
            "category": self.category,
            "expected_action": self.expected_action,
            "actual_action": self.actual_action,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "matched": self.matched,
            "actor": self.actor,
            "source": self.source,
            "mode": self.mode,
            "reason": self.reason,
            "duration_since_previous_ms": self.duration_since_previous_ms,
            "payload": _json_safe(self.payload or {}),
        }


@dataclass(frozen=True)
class TradeReplayMismatch:
    sequence: int
    field: str
    expected: Any
    actual: Any
    severity: str = "error"

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "field": self.field,
            "expected": _json_safe(self.expected),
            "actual": _json_safe(self.actual),
            "severity": self.severity,
        }


@dataclass(frozen=True)
class TradeReplayReport:
    replay_id: str
    session_id: str
    source: str
    generated_utc: str
    expected_step_count: int
    actual_step_count: int
    steps: tuple[TradeReplayStep, ...]
    mismatches: tuple[TradeReplayMismatch, ...]
    timing: dict[str, Any]

    @property
    def passed(self) -> bool:
        return not self.mismatches

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_version": TRADE_REPLAY_PAYLOAD_VERSION,
            "replay_id": self.replay_id,
            "session_id": self.session_id,
            "source": self.source,
            "generated_utc": self.generated_utc,
            "passed": self.passed,
            "expected_step_count": self.expected_step_count,
            "actual_step_count": self.actual_step_count,
            "timing": _json_safe(self.timing),
            "mismatches": [mismatch.as_dict() for mismatch in self.mismatches],
            "steps": [step.as_dict() for step in self.steps],
        }


class TradeReplayHarness:
    def replay_lifecycle_audit(
        self,
        trail: Mapping[str, Any],
        *,
        session_id: str = "",
        expected_path: Sequence[str] | None = None,
    ) -> TradeReplayReport:
        raw_events = _events_from_lifecycle_trail(trail)
        actual_path = tuple(str(event.get("stage", "UNKNOWN")) for event in raw_events)
        path = tuple(expected_path or _expected_lifecycle_path(actual_path))
        expected = [
            {
                "action": action,
                "status": action if action in {"BLOCKED", "REJECTED"} else "RECORDED",
                "category": _category_for_lifecycle_stage(action),
            }
            for action in path
        ]
        actual = [
            {
                "event_id": f"{trail.get('trade_id', 'TRADE')}:{index}:{event.get('stage', 'UNKNOWN')}",
                "timestamp_utc": event.get("timestamp_utc", ""),
                "category": _category_for_lifecycle_stage(str(event.get("stage", "UNKNOWN"))),
                "action": event.get("stage", "UNKNOWN"),
                "status": event.get("status", "RECORDED"),
                "actor": "",
                "source": "trade_lifecycle_audit",
                "mode": event.get("mode", "paper"),
                "reason": event.get("reason", ""),
                "payload": event,
            }
            for index, event in enumerate(raw_events, start=1)
        ]
        return self.compare_expected_to_actual(
            expected,
            actual,
            session_id=session_id or str(trail.get("trade_id", "")),
            source="trade_lifecycle_audit",
        )

    def replay_audit_events(
        self,
        events: Iterable[AuditTrailEvent | Mapping[str, Any]],
        *,
        session_id: str = "AUDIT-SESSION",
        expected_events: Sequence[Mapping[str, Any]] | None = None,
    ) -> TradeReplayReport:
        actual = [_actual_from_audit_event(event) for event in events]
        expected = [
            dict(item)
            for item in expected_events
        ] if expected_events is not None else [
            {
                "action": item.get("action", "UNKNOWN"),
                "status": item.get("status", "UNKNOWN"),
                "category": item.get("category", "execution_attempt"),
            }
            for item in actual
        ]
        return self.compare_expected_to_actual(
            expected,
            actual,
            session_id=session_id,
            source="audit_events",
        )

    def replay_mobile_event_file(
        self,
        path: str | Path,
        *,
        session_id: str = "MOBILE-AUDIT",
        limit: int = 250,
        expected_events: Sequence[Mapping[str, Any]] | None = None,
    ) -> TradeReplayReport:
        events = tuple(reversed(load_mobile_trade_audit_events(path, limit=limit)))
        return self.replay_audit_events(
            events,
            session_id=session_id,
            expected_events=expected_events,
        )

    def compare_expected_to_actual(
        self,
        expected: Sequence[Mapping[str, Any]],
        actual: Sequence[Mapping[str, Any]],
        *,
        session_id: str = "REPLAY-SESSION",
        source: str = "replay_compare",
    ) -> TradeReplayReport:
        expected_count = len(expected)
        actual_count = len(actual)
        steps: list[TradeReplayStep] = []
        mismatches: list[TradeReplayMismatch] = []
        max_count = max(expected_count, actual_count)
        previous_timestamp = ""

        for index in range(max_count):
            expected_item = expected[index] if index < expected_count else {}
            actual_item = actual[index] if index < actual_count else {}
            sequence = index + 1
            expected_action = str(expected_item.get("action", "MISSING"))
            actual_action = str(actual_item.get("action", "MISSING"))
            expected_status = str(expected_item.get("status", "MISSING"))
            actual_status = str(actual_item.get("status", "MISSING"))
            timestamp = str(actual_item.get("timestamp_utc") or expected_item.get("timestamp_utc") or "")
            duration_ms = _duration_ms(previous_timestamp, timestamp)
            previous_timestamp = timestamp or previous_timestamp
            step = TradeReplayStep(
                sequence=sequence,
                step_id=str(actual_item.get("event_id") or expected_item.get("event_id") or f"REPLAY-{sequence:04d}"),
                timestamp_utc=timestamp,
                category=str(actual_item.get("category") or expected_item.get("category") or "execution_attempt"),
                expected_action=expected_action,
                actual_action=actual_action,
                expected_status=expected_status,
                actual_status=actual_status,
                actor=str(actual_item.get("actor", "")),
                source=str(actual_item.get("source", source)),
                mode=str(actual_item.get("mode") or expected_item.get("mode") or "paper"),
                reason=str(actual_item.get("reason", "")),
                duration_since_previous_ms=duration_ms,
                payload=_json_safe(actual_item.get("payload", {})),
            )
            steps.append(step)

            if index >= expected_count:
                mismatches.append(
                    TradeReplayMismatch(sequence, "step_count", "NO_STEP", actual_action)
                )
                continue
            if index >= actual_count:
                mismatches.append(
                    TradeReplayMismatch(sequence, "step_count", expected_action, "MISSING")
                )
                continue
            if expected_action != actual_action:
                mismatches.append(
                    TradeReplayMismatch(sequence, "action", expected_action, actual_action)
                )
            if expected_status != actual_status:
                mismatches.append(
                    TradeReplayMismatch(sequence, "status", expected_status, actual_status)
                )

        timing = _timing_summary(steps)
        return TradeReplayReport(
            replay_id=_replay_id(source, session_id, expected, actual),
            session_id=session_id,
            source=source,
            generated_utc=datetime.now(timezone.utc).isoformat(),
            expected_step_count=expected_count,
            actual_step_count=actual_count,
            steps=tuple(steps),
            mismatches=tuple(mismatches),
            timing=timing,
        )


def replay_lifecycle_audit(
    trail: Mapping[str, Any],
    *,
    session_id: str = "",
    expected_path: Sequence[str] | None = None,
) -> TradeReplayReport:
    return TradeReplayHarness().replay_lifecycle_audit(
        trail,
        session_id=session_id,
        expected_path=expected_path,
    )


def replay_mobile_trade_event_file(
    path: str | Path,
    *,
    session_id: str = "MOBILE-AUDIT",
    limit: int = 250,
    expected_events: Sequence[Mapping[str, Any]] | None = None,
) -> TradeReplayReport:
    return TradeReplayHarness().replay_mobile_event_file(
        path,
        session_id=session_id,
        limit=limit,
        expected_events=expected_events,
    )


def compare_expected_to_actual(
    expected: Sequence[Mapping[str, Any]],
    actual: Sequence[Mapping[str, Any]],
    *,
    session_id: str = "REPLAY-SESSION",
    source: str = "replay_compare",
) -> TradeReplayReport:
    return TradeReplayHarness().compare_expected_to_actual(
        expected,
        actual,
        session_id=session_id,
        source=source,
    )


def reconstruct_replay_state(report: TradeReplayReport | Mapping[str, Any]) -> dict[str, Any]:
    payload = report.as_dict() if isinstance(report, TradeReplayReport) else _json_safe(report)
    steps = payload.get("steps", [])
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        steps = []

    normalized_steps = [step for step in steps if isinstance(step, Mapping)]
    sequences = [_safe_int(step.get("sequence"), 0) for step in normalized_steps]
    lifecycle_path = [str(step.get("actual_action", "UNKNOWN")) for step in normalized_steps]
    governance_events = [
        step
        for step in normalized_steps
        if str(step.get("category", "")).lower() in {"governance", "permission_denial"}
    ]
    broker_events = [
        step
        for step in normalized_steps
        if str(step.get("category", "")).lower() in {"broker", "execution"}
    ]
    blocked_reasons = [
        str(step.get("reason"))
        for step in normalized_steps
        if str(step.get("actual_status", "")).upper() in {"BLOCKED", "REJECTED"}
        and step.get("reason")
    ]

    return {
        "payload_version": "css.trade_replay.reconstruction.v1",
        "replay_id": payload.get("replay_id", ""),
        "session_id": payload.get("session_id", ""),
        "sequence_integrity": sequences == list(range(1, len(sequences) + 1)),
        "lifecycle_path": lifecycle_path,
        "governance_event_count": len(governance_events),
        "broker_event_count": len(broker_events),
        "blocked_reasons": blocked_reasons,
        "modes_observed": sorted({str(step.get("mode", "paper")) for step in normalized_steps}),
    }


def _events_from_lifecycle_trail(trail: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    events = trail.get("events", ())
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        return ()
    return tuple(event for event in events if isinstance(event, Mapping))


def _expected_lifecycle_path(actual_path: Sequence[str]) -> tuple[str, ...]:
    actual = tuple(str(item).upper() for item in actual_path)
    if "BLOCKED" in actual:
        return BLOCKED_LIFECYCLE_PATH
    if "REJECTED" in actual:
        return REJECTED_LIFECYCLE_PATH
    return ACCEPTED_LIFECYCLE_PATH


def _actual_from_audit_event(event: AuditTrailEvent | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(event, AuditTrailEvent):
        payload = event.as_dict()
    elif isinstance(event, Mapping):
        payload = _json_safe(event)
    else:
        payload = {}
    return {
        "event_id": payload.get("event_id", ""),
        "timestamp_utc": payload.get("timestamp_utc", ""),
        "category": payload.get("category", "execution_attempt"),
        "action": payload.get("action", "UNKNOWN"),
        "status": payload.get("status", "UNKNOWN"),
        "actor": payload.get("actor", ""),
        "source": payload.get("source", "audit_events"),
        "mode": _payload_mode(payload),
        "reason": payload.get("reason", ""),
        "payload": payload,
    }


def _payload_mode(payload: Mapping[str, Any]) -> str:
    nested = payload.get("payload")
    ticket = nested.get("ticket", {}) if isinstance(nested, Mapping) else {}
    mode = ticket.get("mode") if isinstance(ticket, Mapping) else ""
    return str(mode or payload.get("mode") or "paper")


def _category_for_lifecycle_stage(stage: str) -> str:
    normalized = stage.strip().upper()
    if normalized == "SIGNAL_RECEIVED":
        return "signal"
    if normalized == "GOVERNANCE_CHECKED":
        return "governance"
    if normalized == "RISK_CHECKED":
        return "risk"
    if normalized in {"BROKER_ROUTE_SELECTED", "ORDER_SUBMITTED", "EXECUTION_REPORTED"}:
        return "execution"
    if normalized == "LEDGER_POSTED":
        return "ledger"
    if normalized == "DASHBOARD_PUBLISHED":
        return "dashboard"
    if normalized in {"BLOCKED", "REJECTED"}:
        return "blocked"
    return "unknown"


def _duration_ms(previous: str, current: str) -> float | None:
    if not previous or not current:
        return None
    previous_dt = _parse_timestamp(previous)
    current_dt = _parse_timestamp(current)
    if not previous_dt or not current_dt:
        return None
    return round(max(0.0, (current_dt - previous_dt).total_seconds() * 1000.0), 3)


def _timing_summary(steps: Sequence[TradeReplayStep]) -> dict[str, Any]:
    timestamps = [
        _parse_timestamp(step.timestamp_utc)
        for step in steps
        if step.timestamp_utc
    ]
    valid_timestamps = [item for item in timestamps if item is not None]
    durations = [
        float(step.duration_since_previous_ms)
        for step in steps
        if step.duration_since_previous_ms is not None
    ]
    if not valid_timestamps:
        return {
            "first_event_utc": "",
            "last_event_utc": "",
            "total_observed_ms": 0.0,
            "max_step_gap_ms": 0.0,
        }
    first = min(valid_timestamps)
    last = max(valid_timestamps)
    return {
        "first_event_utc": first.isoformat(),
        "last_event_utc": last.isoformat(),
        "total_observed_ms": round(max(0.0, (last - first).total_seconds() * 1000.0), 3),
        "max_step_gap_ms": round(max(durations) if durations else 0.0, 3),
    }


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _replay_id(
    source: str,
    session_id: str,
    expected: Sequence[Mapping[str, Any]],
    actual: Sequence[Mapping[str, Any]],
) -> str:
    payload = {
        "source": source,
        "session_id": session_id,
        "expected": _json_safe(expected),
        "actual": _json_safe(actual),
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16].upper()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(key)
            if _is_sensitive_key(safe_key):
                redacted[safe_key] = "REDACTED"
            else:
                redacted[safe_key] = _json_safe(item)
        return redacted
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
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
