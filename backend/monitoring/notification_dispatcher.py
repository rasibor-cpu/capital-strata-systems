from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.monitoring.alert_repository import AlertRepository


class NotificationDispatcherError(Exception):
    """Raised when notification dispatch storage is invalid or unreadable."""


class NotificationDispatcher:
    """Backend-only dispatcher for canonical critical alert notifications."""

    SUPPORTED_CHANNELS = {"FILE_LOG", "CONSOLE_LOG"}

    def __init__(self, storage_dir: str | None = None) -> None:
        self.storage_dir = Path(storage_dir or "runtime/notifications")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.storage_dir / "notifications.jsonl"

    def dispatch_alert(
        self,
        alert: dict[str, Any],
        *,
        channels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_alert = self._normalize_alert(alert)

        if normalized_alert["severity"] != "CRITICAL":
            return []

        if bool(normalized_alert.get("acknowledged", False)):
            return []

        selected_channels = channels or ["FILE_LOG", "CONSOLE_LOG"]
        results: list[dict[str, Any]] = []

        for channel in selected_channels:
            normalized_channel = str(channel or "").strip().upper()
            if normalized_channel not in self.SUPPORTED_CHANNELS:
                raise NotificationDispatcherError("Unsupported notification channel")

            if self._notification_exists(
                alert_id=normalized_alert["alert_id"],
                channel=normalized_channel,
            ):
                continue

            record = {
                "notification_id": str(uuid.uuid4()),
                "alert_id": normalized_alert["alert_id"],
                "timestamp": self._utc_timestamp(),
                "channel": normalized_channel,
                "severity": normalized_alert["severity"],
                "event_type": normalized_alert["event_type"],
                "source": normalized_alert["source"],
                "message": normalized_alert["message"],
                "status": "DISPATCHED",
            }

            if normalized_channel == "FILE_LOG":
                self._write_record(record)
            elif normalized_channel == "CONSOLE_LOG":
                print(
                    "[ALERT_NOTIFICATION] "
                    f"alert_id={record['alert_id']} "
                    f"severity={record['severity']} "
                    f"event_type={record['event_type']} "
                    f"source={record['source']} "
                    f"message={record['message']}"
                )
                self._write_record(record)

            results.append(record)

        return results

    def load_notifications(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []

        records: list[dict[str, Any]] = []
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception as exc:
                        raise NotificationDispatcherError("Corrupt notification storage") from exc

                    if not isinstance(payload, dict):
                        raise NotificationDispatcherError("Corrupt notification storage")

                    records.append(self._normalize_notification(payload))
        except NotificationDispatcherError:
            raise
        except Exception as exc:
            raise NotificationDispatcherError("Invalid notification storage") from exc

        return records

    def _normalize_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(alert, dict):
            raise NotificationDispatcherError("Alert payload must be a dictionary")

        alert_id = str(alert.get("alert_id") or "").strip()
        if not alert_id:
            raise NotificationDispatcherError("Missing alert_id")

        severity = str(alert.get("severity") or "").strip().upper()
        if severity not in {"INFO", "WARNING", "CRITICAL"}:
            raise NotificationDispatcherError("Invalid alert severity")

        event_type = str(alert.get("event_type") or "").strip().upper()
        source = str(alert.get("source") or "").strip()
        message = str(alert.get("message") or "").strip()

        if not event_type:
            raise NotificationDispatcherError("Missing event_type")
        if not source:
            raise NotificationDispatcherError("Missing source")
        if not message:
            raise NotificationDispatcherError("Missing message")

        return {
            "alert_id": alert_id,
            "severity": severity,
            "event_type": event_type,
            "source": source,
            "message": message,
            "acknowledged": bool(alert.get("acknowledged", False)),
        }

    def _normalize_notification(self, payload: dict[str, Any]) -> dict[str, Any]:
        required_fields = {
            "notification_id",
            "alert_id",
            "timestamp",
            "channel",
            "severity",
            "event_type",
            "source",
            "message",
            "status",
        }

        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise NotificationDispatcherError("Corrupt notification storage")

        return {
            "notification_id": str(payload["notification_id"]),
            "alert_id": str(payload["alert_id"]),
            "timestamp": str(payload["timestamp"]),
            "channel": str(payload["channel"]).upper(),
            "severity": str(payload["severity"]).upper(),
            "event_type": str(payload["event_type"]).upper(),
            "source": str(payload["source"]),
            "message": str(payload["message"]),
            "status": str(payload["status"]),
        }

    def _notification_exists(self, *, alert_id: str, channel: str) -> bool:
        notifications = self.load_notifications()
        return any(
            item.get("alert_id") == alert_id and item.get("channel") == channel
            for item in notifications
        )

    def _write_record(self, record: dict[str, Any]) -> None:
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        except Exception as exc:
            raise NotificationDispatcherError("Unable to write notification") from exc

    def _utc_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()


def dispatch_critical_alerts(
    repository: AlertRepository,
    dispatcher: NotificationDispatcher,
    *,
    channels: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Dispatch unacknowledged CRITICAL alerts from repository using dispatcher."""

    dispatched: list[dict[str, Any]] = []
    alerts = repository.list_critical_alerts(limit=10000)

    for alert in alerts:
        if bool(alert.get("acknowledged", False)):
            continue
        dispatched.extend(dispatcher.dispatch_alert(alert, channels=channels))

    return dispatched
