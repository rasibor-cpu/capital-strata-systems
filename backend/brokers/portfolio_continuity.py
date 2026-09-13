from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .readonly_domain import (
    BrokerActivity, BrokerHealth, BrokerPosition, PortfolioSnapshot, SnapshotSource, money, utc,
)


SNAPSHOT_SCHEMA = "css.portfolio_snapshot.v1"
AUDIT_SCHEMA = "css.portfolio_audit.v1"


class SnapshotStoreError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _decimal(value: Any):
    return money(value)


def _datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _position(payload: dict[str, Any]) -> BrokerPosition:
    return BrokerPosition(
        str(payload["account_id"]), str(payload["symbol"]), _decimal(payload["quantity"]) or 0,
        _decimal(payload.get("average_cost")), _decimal(payload.get("market_price")), _decimal(payload.get("market_value")),
        _decimal(payload.get("unrealized_pnl")), _decimal(payload.get("realized_pnl")), str(payload["currency"]), _datetime(payload["as_of_utc"]),
    )


def snapshot_from_dict(payload: dict[str, Any]) -> PortfolioSnapshot:
    try:
        return PortfolioSnapshot(
            account_id_masked=str(payload["account_id_masked"]), as_of_utc=_datetime(payload["as_of_utc"]), base_currency=payload.get("base_currency"),
            cash=_decimal(payload.get("cash")), buying_power=_decimal(payload.get("buying_power")), total_equity=_decimal(payload.get("total_equity")), market_value=_decimal(payload.get("market_value")),
            positions=tuple(_position(item) for item in payload.get("positions", [])), total_realized_pnl=_decimal(payload.get("total_realized_pnl")), total_unrealized_pnl=_decimal(payload.get("total_unrealized_pnl")), total_pnl=_decimal(payload.get("total_pnl")),
            broker_health=BrokerHealth(str(payload.get("broker_health", "UNAVAILABLE"))), broker_data_freshness=str(payload.get("broker_data_freshness", "UNKNOWN")), snapshot_source=SnapshotSource(str(payload.get("snapshot_source", "UNAVAILABLE"))),
            last_successful_sync_utc=_datetime(payload.get("last_successful_sync_utc")), reason=payload.get("reason"), provider=str(payload.get("provider", "UNKNOWN")), snapshot_id=str(payload.get("snapshot_id", "")), prior_snapshot_id=payload.get("prior_snapshot_id"), ingestion_utc=_datetime(payload.get("ingestion_utc")), validation_status=str(payload.get("validation_status", "VALIDATED")), observation_ids=tuple(str(item) for item in payload.get("observation_ids", [])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotStoreError("portfolio snapshot is malformed") from exc


class PortfolioSnapshotStore:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def save(self, snapshot: PortfolioSnapshot) -> None:
        payload = {"schema": SNAPSHOT_SCHEMA, "snapshot": snapshot.as_dict()}
        record = {**payload, "checksum": _checksum(payload)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".portfolio-", dir=self.path.parent, text=True)
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

    def load(self) -> tuple[str, PortfolioSnapshot | None]:
        if not self.path.exists():
            return "UNAVAILABLE", None
        try:
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if record.get("schema") != SNAPSHOT_SCHEMA or record.get("checksum") != _checksum({"schema": record.get("schema"), "snapshot": record.get("snapshot")}):
                return "CORRUPT", None
            return "LAST_KNOWN_GOOD_STALE", snapshot_from_dict(record["snapshot"])
        except (OSError, ValueError, TypeError, SnapshotStoreError, KeyError):
            return "CORRUPT", None


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    timestamp_utc: datetime
    snapshot_id: str | None
    account_reference: str
    severity: str
    explanation: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": AUDIT_SCHEMA, "event_id": self.event_id, "event_type": self.event_type, "timestamp_utc": self.timestamp_utc.isoformat(), "snapshot_id": self.snapshot_id, "account_reference": self.account_reference, "severity": self.severity, "explanation": self.explanation}


class AuditHistory:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def append(self, event: AuditEvent) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = {item.get("event_id") for item in self.read()}
        if event.event_id in existing:
            return False
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(event.as_dict()) + "\n")
        return True

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line:
                payload = json.loads(line)
                if payload.get("schema") != AUDIT_SCHEMA:
                    raise SnapshotStoreError("audit history schema is invalid")
                events.append(payload)
        return events


class PortfolioContinuity:
    def __init__(self, store: PortfolioSnapshotStore, audit: AuditHistory) -> None:
        self.store = store
        self.audit = audit
        self._seen: set[str] = set()

    def accept(self, snapshot: PortfolioSnapshot, *, now: datetime | None = None, observation_ids: tuple[str, ...] = ()) -> bool:
        if observation_ids:
            snapshot = replace(snapshot, observation_ids=tuple(observation_ids))
        identity = snapshot.snapshot_id or _checksum(snapshot.as_dict())
        if identity in self._seen:
            return False
        self._seen.add(identity)
        self.store.save(snapshot)
        timestamp = utc(now or datetime.now(timezone.utc))
        self.audit.append(AuditEvent("snapshot-" + identity, "SNAPSHOT_ACCEPTED", timestamp, identity, snapshot.account_id_masked, "info", "Validated portfolio snapshot accepted."))
        return True

    def reload(self, *, now: datetime | None = None) -> tuple[str, PortfolioSnapshot | None]:
        status, snapshot = self.store.load()
        timestamp = utc(now or datetime.now(timezone.utc))
        if snapshot is not None:
            snapshot = replace(snapshot, snapshot_source=SnapshotSource.STALE, broker_data_freshness="STALE", validation_status="RELOADED_STALE", reason="RELOADED_LAST_KNOWN_GOOD")
            self.audit.append(AuditEvent("reload-" + (snapshot.snapshot_id or _checksum(snapshot.as_dict())), "SNAPSHOT_RELOADED", timestamp, snapshot.snapshot_id, snapshot.account_id_masked, "warning", "Last-known-good snapshot reloaded; provider freshness is not asserted."))
        elif status == "CORRUPT":
            self.audit.append(AuditEvent("snapshot-corrupt", "SNAPSHOT_REJECTED", timestamp, None, "<unknown>", "error", "Persisted portfolio snapshot failed integrity validation."))
        return status, snapshot


__all__ = ["AUDIT_SCHEMA", "SNAPSHOT_SCHEMA", "AuditEvent", "AuditHistory", "PortfolioContinuity", "PortfolioSnapshotStore", "SnapshotStoreError", "snapshot_from_dict"]