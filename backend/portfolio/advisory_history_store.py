from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping


class AdvisoryHistoryStoreError(RuntimeError):
    """Fail-closed exception for advisory history persistence."""


class AdvisoryHistoryStore:
    """Safe JSONL-style advisory history stored as a JSON list."""

    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        self.path = os.path.join(storage_dir, "advisory_history.json")

    def append_decision(self, decision: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(decision, Mapping):
            return self._status("DATA UNAVAILABLE", "decision_malformed")
        rows = self._read_rows()
        record = dict(decision)
        record.setdefault("id", f"advisory-{len(rows) + 1}")
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        record.setdefault("advisory_only", True)
        rows.append(record)
        self._write_rows(rows)
        return {"status": "OK", "record": record, "count": len(rows), "advisory_only": True}

    def list_recent(self, limit: int = 10) -> dict[str, Any]:
        rows = self._read_rows()
        safe_limit = max(1, int(limit or 10))
        return {"status": "OK", "decisions": rows[-safe_limit:], "count": len(rows), "advisory_only": True}

    def summarize(self) -> dict[str, Any]:
        rows = self._read_rows()
        counts: dict[str, int] = {}
        for row in rows:
            recommendation = str(row.get("adaptive_recommendation", row.get("recommendation", "UNKNOWN"))).upper()
            counts[recommendation] = counts.get(recommendation, 0) + 1
        return {
            "status": "OK",
            "total_decisions": len(rows),
            "recommendation_counts": {key: counts[key] for key in sorted(counts.keys())},
            "advisory_only": True,
        }

    def _read_rows(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, list):
                return []
            return [row for row in payload if isinstance(row, dict)]
        except Exception:
            return []

    def _write_rows(self, rows: list[dict[str, Any]]) -> None:
        os.makedirs(self.storage_dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2, sort_keys=True)

    @staticmethod
    def _status(status: str, reason: str) -> dict[str, Any]:
        return {"status": status, "reason": reason, "advisory_only": True}
