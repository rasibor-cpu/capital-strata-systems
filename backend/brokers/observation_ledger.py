from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .portfolio_continuity import SnapshotStoreError, _canonical, _checksum
from .readonly_domain import PortfolioSnapshot, utc


LEDGER_SCHEMA = "css.broker_observation_ledger.v1"
RECONCILIATION_SCHEMA = "css.reconciliation_ledger.v1"

SENSITIVE_KEY_PARTS = (
    "access_token",
    "refresh_token",
    "authorization",
    "bearer",
    "api_key",
    "api_secret",
    "client_secret",
    "password",
    "private_key",
    "credential",
    "secret",
    "token",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, Mapping):
        return {
            str(key): ("REDACTED" if _is_sensitive_key(str(key)) else _safe(item))
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    return str(value) if type(value).__name__ == "Decimal" else value


@dataclass(frozen=True)
class BrokerObservation:
    observation_type: str
    provider: str
    masked_account_id: str
    observed_at_utc: datetime
    snapshot_id: str | None
    payload: Mapping[str, Any]
    provider_entity_id: str | None = None
    observation_id: str = ""
    ingested_at_utc: datetime | None = None
    schema_version: str = LEDGER_SCHEMA

    def canonical_payload(self) -> dict[str, Any]:
        return {"observation_type": self.observation_type, "provider": self.provider, "masked_account_id": self.masked_account_id, "provider_entity_id": self.provider_entity_id, "observed_at_utc": utc(self.observed_at_utc).isoformat(), "snapshot_id": self.snapshot_id, "payload": _safe(self.payload), "schema_version": self.schema_version}

    def with_identity(self, *, ingested_at: datetime | None = None) -> "BrokerObservation":
        identity = self.observation_id or hashlib.sha256(_canonical(self.canonical_payload()).encode("utf-8")).hexdigest()
        return replace(self, observation_id=identity, ingested_at_utc=utc(ingested_at or self.ingested_at_utc or datetime.now(timezone.utc)))

    def as_dict(self) -> dict[str, Any]:
        item = self.with_identity()
        return {**item.canonical_payload(), "observation_id": item.observation_id, "ingested_at_utc": item.ingested_at_utc.isoformat() if item.ingested_at_utc else None, "payload_hash": hashlib.sha256(_canonical(_safe(item.payload)).encode("utf-8")).hexdigest()}


class ObservationLedger:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._records: list[dict[str, Any]] = []
        self._duplicate_count = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if record.get("schema") != LEDGER_SCHEMA or record.get("checksum") != _checksum({"schema": record.get("schema"), "entries": record.get("entries")}):
                raise SnapshotStoreError("observation ledger integrity validation failed")
            self._records = list(record.get("entries", []))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise SnapshotStoreError("observation ledger is corrupt") from exc

    def _persist(self) -> None:
        payload = {"schema": LEDGER_SCHEMA, "entries": self._records}
        record = {**payload, "checksum": _checksum(payload)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".observation-", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def append(self, observation: BrokerObservation) -> bool:
        normalized = observation.with_identity()
        if any(item.get("observation_id") == normalized.observation_id for item in self._records):
            self._duplicate_count += 1
            return False
        self._records.append(normalized.as_dict())
        self._persist()
        return True

    @property
    def entry_count(self) -> int:
        return len(self._records)

    @property
    def duplicate_count(self) -> int:
        return self._duplicate_count

    def entries(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._records]


class ReconciliationLedger:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if record.get("schema") != RECONCILIATION_SCHEMA or record.get("checksum") != _checksum({"schema": record.get("schema"), "entries": record.get("entries")}):
                raise SnapshotStoreError("reconciliation ledger integrity validation failed")
            self._records = dict(record.get("entries", {}))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise SnapshotStoreError("reconciliation ledger is corrupt") from exc

    def _persist(self) -> None:
        payload = {"schema": RECONCILIATION_SCHEMA, "entries": self._records}
        record = {**payload, "checksum": _checksum(payload)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(_canonical(record), encoding="utf-8")
        os.replace(temporary, self.path)

    def observe(self, evidence_key: str, *, status: str, stale: bool = False) -> str:
        previous = self._records.get(evidence_key)
        if stale and previous is not None:
            return "UNCHANGED"
        if previous is None:
            lifecycle = "CREATED"
        elif previous.get("status") == status:
            lifecycle = "UNCHANGED"
        elif status == "MATCH":
            lifecycle = "RESOLVED"
        else:
            lifecycle = "REOPENED"
        self._records[evidence_key] = {"status": status, "lifecycle": lifecycle, "stale": stale}
        self._persist()
        return lifecycle

    def entries(self) -> dict[str, dict[str, Any]]:
        return dict(self._records)


__all__ = ["BrokerObservation", "ObservationLedger", "ReconciliationLedger", "LEDGER_SCHEMA", "RECONCILIATION_SCHEMA"]
