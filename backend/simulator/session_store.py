from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from .interactive import InteractiveScenarioSession, InteractiveStatus


SESSION_SCHEMA_VERSION = 1


class InteractiveSessionStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, session: InteractiveScenarioSession) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "learner_id": session.learner_id,
            "scenario_id": session.scenario_id,
            "step_index": session.step_index,
            "status": session.status.value,
            "started_at_utc": session.started_at_utc.isoformat(),
            "updated_at_utc": session.updated_at_utc.isoformat(),
            "completed_at_utc": session.completed_at_utc.isoformat()
            if session.completed_at_utc
            else None,
            "decision_ids": list(session.decision_ids),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            handle.write(encoded)
            temp_name = handle.name
        os.replace(temp_name, self.path)

    def load(self) -> InteractiveScenarioSession:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SESSION_SCHEMA_VERSION:
            raise ValueError("unsupported interactive session schema")
        completed = payload.get("completed_at_utc")
        return InteractiveScenarioSession(
            learner_id=payload["learner_id"],
            scenario_id=payload["scenario_id"],
            step_index=int(payload["step_index"]),
            status=InteractiveStatus(payload["status"]),
            started_at_utc=datetime.fromisoformat(payload["started_at_utc"]),
            updated_at_utc=datetime.fromisoformat(payload["updated_at_utc"]),
            completed_at_utc=datetime.fromisoformat(completed) if completed else None,
            decision_ids=tuple(payload.get("decision_ids", [])),
        )
