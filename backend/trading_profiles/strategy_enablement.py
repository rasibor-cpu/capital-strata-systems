"""Strategy enablement registry for B1. Missing or disabled => fail closed (not routable)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.certification.ov002_persistence import PersistenceError, atomic_write_json, read_json_object
from backend.runtime.interprocess_lock import exclusive_file_lock

SCHEMA = "css.trading_profiles.strategy_enablement.v1"
DEFAULT_NAME = "strategy_enablement.json"


class StrategyEnablement:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.path = self.root / DEFAULT_NAME
        self.lock_path = self.root / "strategy_enablement.lock"

    def _empty(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "strategies": {}}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            doc = read_json_object(self.path)
        except PersistenceError:
            return self._empty()
        if doc.get("schema") != SCHEMA or not isinstance(doc.get("strategies"), dict):
            return self._empty()
        return doc

    def _write(self, doc: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            atomic_write_json(self.path, doc, expected_root=self.root)

    def is_enabled(self, strategy_id: str) -> bool:
        row = self._read()["strategies"].get(str(strategy_id))
        return bool(isinstance(row, dict) and row.get("enabled") is True)

    def enable(self, strategy_id: str, *, reason: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
        doc = self._read()
        row = {
            "enabled": True,
            "reason": str(reason)[:500],
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics or {},
        }
        doc["strategies"][str(strategy_id)] = row
        self._write(doc)
        return row

    def disable(self, strategy_id: str, *, reason: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
        doc = self._read()
        row = {
            "enabled": False,
            "reason": str(reason)[:500],
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics or {},
        }
        doc["strategies"][str(strategy_id)] = row
        self._write(doc)
        return row

    def status(self, strategy_id: str) -> dict[str, Any]:
        row = self._read()["strategies"].get(str(strategy_id))
        if not isinstance(row, dict):
            return {"strategy_id": strategy_id, "enabled": False, "reason": "strategy_not_registered"}
        return {"strategy_id": strategy_id, **row}
