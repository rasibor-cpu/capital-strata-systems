from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AlertRepositoryError(Exception):
    """Raised when alert storage is unreadable or corrupt."""


class AlertRepository:
    """Canonical repository for critical runtime and trading alerts."""

    CRITICAL_EVENT_TYPES = {
        "RUNTIME_FAILURE",
        "SUPERVISOR_RECOVERY",
        "BROKER_DISCONNECT",
        "TRADE_REJECTED",
        "RISK_GATE_BLOCK",
        "LIVE_MODE_BLOCKED",
        "DATA_UNAVAILABLE",
        "PNL_DRAWDOWN",
        "HEARTBEAT_STALE",
    }

    SEVERITIES = {"INFO", "WARNING", "CRITICAL"}

    def __init__(self, storage_dir: str | None = None) -> None:
        self.storage_dir = Path(storage_dir or "runtime/alerts")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def persist_alert(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_payload(payload)
        dedupe_key = str(normalized["dedupe_key"] or "").strip()

        if dedupe_key:
            existing = self._load_existing_by_dedupe_key(dedupe_key)
            if existing is not None:
                return existing

        alert_id = str(normalized.get("alert_id") or uuid.uuid4())
        timestamp = normalized.get("timestamp") or self._utc_timestamp()
        record = {
            "alert_id": alert_id,
            "timestamp": timestamp,
            "severity": normalized["severity"],
            "event_type": normalized["event_type"],
            "source": normalized["source"],
            "message": normalized["message"],
            "details": normalized["details"],
            "acknowledged": bool(normalized.get("acknowledged", False)),
            "dedupe_key": dedupe_key,
        }

        storage_path = self.storage_dir / f"{alert_id}.json"
        try:
            with storage_path.open("w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
        except Exception as exc:  # pragma: no cover - defensive file failure
            raise AlertRepositoryError(f"Unable to persist alert: {exc}") from exc

        return record

    def load_alerts(self) -> list[dict[str, Any]]:
        if not self.storage_dir.exists():
            return []

        alerts: list[dict[str, Any]] = []
        for path in sorted(self.storage_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except Exception as exc:
                raise AlertRepositoryError(f"Corrupt storage: {path.name}") from exc

            if not isinstance(payload, dict):
                raise AlertRepositoryError(f"Corrupt storage: {path.name}")

            alerts.append(self._normalize_payload(payload, require_existing=True))

        return sorted(alerts, key=lambda item: item["timestamp"], reverse=True)

    def list_recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        alerts = self.load_alerts()
        return alerts[: max(0, int(limit))]

    def list_critical_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        alerts = [
            alert for alert in self.load_alerts() if alert.get("severity") == "CRITICAL"
        ]
        return alerts[: max(0, int(limit))]

    def acknowledge_alert(self, alert_id: str) -> bool:
        alert_id = str(alert_id or "").strip()
        if not alert_id:
            return False

        alerts = self.load_alerts()
        for alert in alerts:
            if alert.get("alert_id") == alert_id:
                updated = dict(alert)
                updated["acknowledged"] = True
                self._write_record(updated)
                return True

        return False

    def _normalize_payload(self, payload: dict[str, Any], require_existing: bool = False) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AlertRepositoryError("Alert payload must be a dictionary")

        severity = str(payload.get("severity") or "").strip().upper()
        if severity not in self.SEVERITIES:
            raise AlertRepositoryError("Invalid severity")

        event_type = str(payload.get("event_type") or "").strip().upper()
        if not event_type:
            raise AlertRepositoryError("Missing event_type")

        source = str(payload.get("source") or "").strip()
        if not source:
            raise AlertRepositoryError("Missing source")

        message = str(payload.get("message") or "").strip()
        if not message:
            raise AlertRepositoryError("Missing message")

        details = payload.get("details")
        if details is None:
            details = {}
        if not isinstance(details, dict):
            raise AlertRepositoryError("Invalid details")

        dedupe_key = str(payload.get("dedupe_key") or "").strip()
        if not dedupe_key and not require_existing:
            dedupe_key = f"{event_type}:{source}:{message}"

        return {
            "alert_id": str(payload.get("alert_id") or ""),
            "timestamp": str(payload.get("timestamp") or self._utc_timestamp()),
            "severity": severity,
            "event_type": event_type,
            "source": source,
            "message": message,
            "details": details,
            "acknowledged": bool(payload.get("acknowledged", False)),
            "dedupe_key": dedupe_key,
        }

    def _load_existing_by_dedupe_key(self, dedupe_key: str) -> dict[str, Any] | None:
        for alert in self.load_alerts():
            if alert.get("dedupe_key") == dedupe_key:
                return alert
        return None

    def _write_record(self, record: dict[str, Any]) -> None:
        storage_path = self.storage_dir / f"{record['alert_id']}.json"
        with storage_path.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)

    def _utc_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class AlertCentreCompatibilityAdapter:
    """Compatibility adapter for mobile/runtime alert consumers."""

    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    def build_payload(self, limit: int = 50) -> list[dict[str, Any]]:
        alerts = self.repository.list_recent_alerts(limit=limit)
        return [
            {
                "alert_id": alert["alert_id"],
                "timestamp": alert["timestamp"],
                "severity": alert["severity"],
                "event_type": alert["event_type"],
                "source": alert["source"],
                "message": alert["message"],
                "details": alert["details"],
                "acknowledged": alert["acknowledged"],
                "dedupe_key": alert["dedupe_key"],
            }
            for alert in alerts
        ]
