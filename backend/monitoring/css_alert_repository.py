from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CSSAlertRepository:
    """
    Repository for persisted CSS runtime alerts.

    Current storage format:
    - one JSON file per alert
    - default directory: runtime/alerts

    This repository is intentionally passive:
    - no broker calls
    - no trade execution
    - no risk changes
    - no authentication changes
    """

    def __init__(self, storage_dir: str | None = None):
        self.storage_dir = Path(storage_dir or "runtime/alerts")

    def list_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.storage_dir.exists():
            return []

        alerts: list[dict[str, Any]] = []

        for path in sorted(self.storage_dir.glob("*.json"), reverse=True):
            try:
                with path.open("r", encoding="utf-8") as file:
                    alert = json.load(file)

                if isinstance(alert, dict):
                    alert.setdefault("acknowledged", False)
                    alerts.append(alert)
            except Exception:
                continue

            if len(alerts) >= limit:
                break

        return alerts

    def get_unread_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        unread: list[dict[str, Any]] = []

        for alert in self.list_alerts(limit=10000):
            if not bool(alert.get("acknowledged", False)):
                unread.append(alert)

            if len(unread) >= limit:
                break

        return unread

    def acknowledge_alert(self, alert_id: str) -> bool:
        if not self.storage_dir.exists():
            return False

        target_alert_id = str(alert_id or "").strip()
        if not target_alert_id:
            return False

        for path in self.storage_dir.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as file:
                    alert = json.load(file)

                if not isinstance(alert, dict):
                    continue

                if str(alert.get("alert_id", "")) != target_alert_id:
                    continue

                alert["acknowledged"] = True

                with path.open("w", encoding="utf-8") as file:
                    json.dump(alert, file, indent=2, sort_keys=True)

                return True
            except Exception:
                continue

        return False

    def purge_old_alerts(self, keep_latest: int = 500) -> int:
        if not self.storage_dir.exists():
            return 0

        files = sorted(self.storage_dir.glob("*.json"), reverse=True)

        if keep_latest < 0:
            keep_latest = 0

        purge_targets = files[keep_latest:]
        purged = 0

        for path in purge_targets:
            try:
                path.unlink()
                purged += 1
            except Exception:
                continue

        return purged