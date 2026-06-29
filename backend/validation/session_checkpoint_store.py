from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from backend.validation.continuous_paper_validation import ContinuousPaperValidation


class SessionCheckpointStoreError(RuntimeError):
    """Fail-closed exception for paper validation checkpoint storage."""


class SessionCheckpointStore:
    """JSON-backed checkpoint store under artifacts/validation."""

    def __init__(self, storage_dir: str | Path):
        self.storage_dir = Path(storage_dir)
        self.path = self.storage_dir / "paper_validation_checkpoints.json"

    def append_checkpoint(self, checkpoint: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(checkpoint, Mapping):
            return self._status("DATA UNAVAILABLE", "checkpoint_malformed", checkpoints=[])
        rows = self._read_rows()
        record = dict(checkpoint)
        record.setdefault("session_id", "paper-validation")
        record.setdefault("timestamp", self._utc_now())
        record.setdefault("paper_validation_only", True)
        record.setdefault("advisory_only", True)
        record.setdefault("execution_allowed", False)
        rows.append(record)
        self._write_rows(rows)
        return {
            "status": "OK",
            "checkpoint": record,
            "count": len(rows),
            "advisory_only": True,
            "paper_validation_only": True,
            "execution_allowed": False,
        }

    def list_checkpoints(self, session_id: str | None = None) -> dict[str, Any]:
        rows = self._read_rows()
        if session_id:
            rows = [row for row in rows if str(row.get("session_id") or "") == str(session_id)]
        return {
            "status": "OK",
            "checkpoints": rows,
            "count": len(rows),
            "advisory_only": True,
            "paper_validation_only": True,
            "execution_allowed": False,
        }

    def summarize_session(self, session_id: str | None = None) -> dict[str, Any]:
        rows = self.list_checkpoints(session_id=session_id).get("checkpoints", [])
        return ContinuousPaperValidation().summarize(rows, session_id=session_id)

    def _read_rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [row for row in payload if isinstance(row, dict)]

    def _write_rows(self, rows: list[dict[str, Any]]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.storage_dir, delete=False) as tmp:
            json.dump(rows, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp_name = tmp.name
        os.replace(tmp_name, self.path)

    @staticmethod
    def _status(status: str, reason: str, **payload: Any) -> dict[str, Any]:
        return {
            "status": status,
            "reason": reason,
            "advisory_only": True,
            "paper_validation_only": True,
            "execution_allowed": False,
            **payload,
        }

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
