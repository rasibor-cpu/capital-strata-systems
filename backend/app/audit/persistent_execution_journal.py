from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.evidence_hashing import hash_evidence_payload


JOURNAL_VERSION = "css.persistent_execution_journal.v1"
DEFAULT_EVENT_TYPE = "EXECUTION_DECISION_AUDIT"
RETENTION_POLICY = "APPEND_ONLY_NO_AUTOMATIC_RETENTION"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "pem",
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
_PUBLIC_SAFETY_KEYS = {
    "broker_mutation_allowed",
    "execution_allowed",
    "mutation_allowed",
    "order_submit_allowed",
    "persistence_enabled",
    "trading_armed",
}


class ExecutionJournalValidationError(ValueError):
    """Raised when a journal record cannot satisfy the audit schema."""


@dataclass(frozen=True)
class PersistentExecutionJournalRecord:
    journal_version: str
    sequence: int
    timestamp_utc: str
    event_type: str
    strategy_id: str
    asset_class: str
    execution_intent: str
    broker_mode: str
    broker_name: str
    decision: str
    reason: str
    correlation_id: str
    evidence_hash: str
    evidence_hash_id: str
    evidence_algorithm: str
    retention_policy: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PersistentExecutionJournal:
    """
    Append-only execution audit journal.

    PCNRASS/MAEP boundary:
    - no broker imports or broker calls
    - no execution routing decisions
    - no live-trading control mutation
    - no credential reads
    - no runtime database writes
    """

    def __init__(self, journal_path: str | Path) -> None:
        self.journal_path = Path(journal_path)

    def append_record(
        self,
        *,
        event_type: str = DEFAULT_EVENT_TYPE,
        strategy_id: str = "",
        asset_class: str,
        execution_intent: str,
        broker_mode: str,
        broker_name: str,
        decision: str,
        reason: str = "",
        correlation_id: str = "",
        metadata: Mapping[str, Any] | None = None,
        timestamp_utc: str = "",
        evidence_hash: str | Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata_safe = _json_safe(dict(metadata or {}))
        sequence = self._next_sequence()
        timestamp = _timestamp(timestamp_utc)
        evidence = self._resolve_evidence_hash(
            event_type=event_type,
            strategy_id=strategy_id,
            asset_class=asset_class,
            execution_intent=execution_intent,
            broker_mode=broker_mode,
            broker_name=broker_name,
            decision=decision,
            reason=reason,
            correlation_id=correlation_id,
            metadata=metadata_safe,
            evidence_hash=evidence_hash,
        )

        record = PersistentExecutionJournalRecord(
            journal_version=JOURNAL_VERSION,
            sequence=sequence,
            timestamp_utc=timestamp,
            event_type=_required_text(event_type, "event_type").upper(),
            strategy_id=str(strategy_id or "").strip(),
            asset_class=_required_text(asset_class, "asset_class").upper(),
            execution_intent=_required_text(execution_intent, "execution_intent").upper(),
            broker_mode=_required_text(broker_mode, "broker_mode").lower(),
            broker_name=_required_text(broker_name, "broker_name").upper(),
            decision=_required_text(decision, "decision").upper(),
            reason=str(reason or "").strip(),
            correlation_id=str(correlation_id or "").strip(),
            evidence_hash=str(evidence["evidence_hash"]),
            evidence_hash_id=str(evidence["evidence_hash_id"]),
            evidence_algorithm=str(evidence["algorithm"]),
            retention_policy=RETENTION_POLICY,
            metadata=metadata_safe,
        )
        line = canonical_record_json(record.as_dict())
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        return record.as_dict()

    def read_records(self, *, strict: bool = False) -> list[dict[str, Any]]:
        if not self.journal_path.exists():
            return []

        records: list[dict[str, Any]] = []
        with self.journal_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                    self.validate_record(record)
                except Exception as exc:
                    if strict:
                        raise ExecutionJournalValidationError(
                            f"Malformed journal line {line_number}: {exc}"
                        ) from exc
                    continue
                records.append(record)
        return records

    def replay_records(self) -> list[dict[str, Any]]:
        return sorted(
            self.read_records(strict=False),
            key=lambda record: int(record.get("sequence", 0)),
        )

    def total_records(self) -> int:
        return len(self.read_records(strict=False))

    def validate_record(self, record: Mapping[str, Any]) -> None:
        missing = [
            field
            for field in (
                "journal_version",
                "sequence",
                "timestamp_utc",
                "event_type",
                "asset_class",
                "execution_intent",
                "broker_mode",
                "broker_name",
                "decision",
                "evidence_hash",
                "evidence_hash_id",
                "evidence_algorithm",
                "retention_policy",
                "metadata",
            )
            if field not in record
        ]
        if missing:
            raise ExecutionJournalValidationError(
                f"Missing required journal fields: {', '.join(missing)}"
            )
        if record.get("journal_version") != JOURNAL_VERSION:
            raise ExecutionJournalValidationError("Unsupported journal version")
        if record.get("retention_policy") != RETENTION_POLICY:
            raise ExecutionJournalValidationError("Unsupported retention policy")
        if record.get("evidence_algorithm") != "sha256":
            raise ExecutionJournalValidationError("Unsupported evidence algorithm")
        if not isinstance(record.get("metadata"), Mapping):
            raise ExecutionJournalValidationError("metadata must be a mapping")
        try:
            sequence = int(record.get("sequence"))
        except Exception as exc:
            raise ExecutionJournalValidationError("sequence must be an integer") from exc
        if sequence < 1:
            raise ExecutionJournalValidationError("sequence must be positive")
        for field in ("event_type", "asset_class", "execution_intent", "broker_mode", "broker_name", "decision"):
            _required_text(record.get(field), field)

    def _next_sequence(self) -> int:
        records = self.read_records(strict=False)
        if not records:
            return 1
        return max(int(record.get("sequence", 0)) for record in records) + 1

    def _resolve_evidence_hash(
        self,
        *,
        event_type: str,
        strategy_id: str,
        asset_class: str,
        execution_intent: str,
        broker_mode: str,
        broker_name: str,
        decision: str,
        reason: str,
        correlation_id: str,
        metadata: Mapping[str, Any],
        evidence_hash: str | Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(evidence_hash, Mapping):
            required = ("evidence_hash", "evidence_hash_id", "algorithm")
            if all(key in evidence_hash for key in required):
                return {
                    "evidence_hash": str(evidence_hash["evidence_hash"]),
                    "evidence_hash_id": str(evidence_hash["evidence_hash_id"]),
                    "algorithm": str(evidence_hash["algorithm"]),
                }
        if isinstance(evidence_hash, str) and evidence_hash.strip():
            text = evidence_hash.strip()
            return {
                "evidence_hash": text,
                "evidence_hash_id": f"EVHASH-{text[:20].upper()}",
                "algorithm": "sha256",
            }

        payload = stable_evidence_payload(
            event_type=event_type,
            strategy_id=strategy_id,
            asset_class=asset_class,
            execution_intent=execution_intent,
            broker_mode=broker_mode,
            broker_name=broker_name,
            decision=decision,
            reason=reason,
            correlation_id=correlation_id,
            metadata=metadata,
        )
        return hash_evidence_payload(
            payload,
            source_type="persistent_execution_journal",
            source_reference=str(correlation_id or execution_intent or "execution_record"),
        )


def stable_evidence_payload(
    *,
    event_type: str = DEFAULT_EVENT_TYPE,
    strategy_id: str = "",
    asset_class: str,
    execution_intent: str,
    broker_mode: str,
    broker_name: str,
    decision: str,
    reason: str = "",
    correlation_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "journal_version": JOURNAL_VERSION,
        "event_type": _required_text(event_type, "event_type").upper(),
        "strategy_id": str(strategy_id or "").strip(),
        "asset_class": _required_text(asset_class, "asset_class").upper(),
        "execution_intent": _required_text(execution_intent, "execution_intent").upper(),
        "broker_mode": _required_text(broker_mode, "broker_mode").lower(),
        "broker_name": _required_text(broker_name, "broker_name").upper(),
        "decision": _required_text(decision, "decision").upper(),
        "reason": str(reason or "").strip(),
        "correlation_id": str(correlation_id or "").strip(),
        "metadata": _json_safe(dict(metadata or {})),
    }


def canonical_record_json(record: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_safe(record),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _timestamp(value: str = "") -> str:
    text = str(value or "").strip()
    if text:
        return text
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExecutionJournalValidationError(f"{field_name} is required")
    return text


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED" if _is_sensitive_key(str(key)) else _json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, Path)):
        return str(value)
    if isinstance(value, str) and _contains_sensitive_marker(value):
        return "REDACTED"
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in _PUBLIC_SAFETY_KEYS:
        return False
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _contains_sensitive_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_VALUE_MARKERS)


__all__ = [
    "DEFAULT_EVENT_TYPE",
    "JOURNAL_VERSION",
    "RETENTION_POLICY",
    "ExecutionJournalValidationError",
    "PersistentExecutionJournal",
    "PersistentExecutionJournalRecord",
    "canonical_record_json",
    "stable_evidence_payload",
]
