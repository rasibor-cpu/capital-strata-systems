from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CSSAlertRepository:
    """
    Read-only repository for persisted CSS runtime alerts.
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
                    alerts.append(json.load(file))
            except Exception:
                continue

            if len(alerts) >= limit:
                break

        return alerts
