from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .event_models import IntelligenceEvent

_STORAGE_FILE_NAME = "gie_intelligence_events.json"


class EventPersistenceEngine:
    def __init__(self, storage_path: str | None = None) -> None:
        self.storage_path = Path(storage_path or Path(__file__).resolve().parent / _STORAGE_FILE_NAME)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        if not self.storage_path.exists():
            self._save_data({"events": [], "archive": [], "snapshots": []})

    def _load_data(self) -> dict[str, list[Any]]:
        try:
            with self.storage_path.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except Exception:
            return {"events": [], "archive": [], "snapshots": []}

    def _save_data(self, data: dict[str, list[Any]]) -> None:
        try:
            with self.storage_path.open("w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, default=str)
        except Exception:
            pass

    def _to_dict(self, event: Any) -> dict[str, Any]:
        if not isinstance(event, IntelligenceEvent):
            return {}
        return {
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "title": event.title,
            "category": event.category.value,
            "severity": event.severity.name,
            "confidence": float(event.confidence or 0.0),
            "raw_confidence": float(getattr(event, "raw_confidence", event.confidence or 0.0)),
            "source": event.source,
            "affected_assets": list(event.affected_assets or []),
            "description": event.description,
            "active": bool(event.active),
            "expiration_time": event.expiration_time.isoformat() if event.expiration_time else None,
            "event_state": event.event_state.name if hasattr(event, "event_state") else "NEW",
            "cooldown_until": event.cooldown_until.isoformat() if hasattr(event, "cooldown_until") and event.cooldown_until else None,
        }

    def save_event(self, event: IntelligenceEvent) -> bool:
        if not isinstance(event, IntelligenceEvent):
            return False

        now = datetime.now(timezone.utc)
        data = self._load_data()
        payload = self._to_dict(event)
        snapshot = {"snapshot_time": now.isoformat(), "event": payload}

        data.setdefault("events", []).append(payload)
        data.setdefault("snapshots", []).append(snapshot)

        self._save_data(data)
        return True

    def load_recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        data = self._load_data()
        events = data.get("events", [])
        return events[-limit:]

    def archive_expired_events(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        data = self._load_data()
        events = data.get("events", [])
        archive = data.get("archive", [])
        expired_events: list[dict[str, Any]] = []

        for event in events:
            expiration_time = event.get("expiration_time")
            active = event.get("active", True)
            if not active:
                expired_events.append(event)
                continue
            if expiration_time:
                try:
                    expiration_dt = datetime.fromisoformat(expiration_time)
                    if expiration_dt.tzinfo is None:
                        expiration_dt = expiration_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if expiration_dt <= now:
                    event["active"] = False
                    event["event_state"] = "EXPIRED"
                    expired_events.append(event)

        if not expired_events:
            return 0

        data["archive"] = archive + expired_events
        data["events"] = [event for event in events if event not in expired_events]
        self._save_data(data)
        return len(expired_events)
