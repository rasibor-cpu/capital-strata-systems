"""
Replay Loader – Strict, Fail-Closed
----------------------------------

Purpose:
- Load persisted replay records by ENGINE_RUN_ID
- Enforce strict schema validation
- Fail closed on missing or malformed data
- NEVER execute trades or touch brokers

This module is READ-ONLY.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any


class ReplayLoaderError(RuntimeError):
    pass


REQUIRED_TOP_LEVEL_FIELDS = {
    "engine_run_id",
    "stored_at_utc",
    "decision_envelope",
    "firewall_result",
    "execution_result",
    "metadata",
}


class ReplayLoader:
    def __init__(self, base_dir: str = "audit_logs"):
        self.base_dir = base_dir
        self.replay_path = os.path.join(self.base_dir, "replays.jsonl")

        if not os.path.exists(self.replay_path):
            raise ReplayLoaderError(
                f"Replay store not found at {self.replay_path}"
            )

    def _validate_record(self, record: Dict[str, Any]) -> None:
        missing = REQUIRED_TOP_LEVEL_FIELDS - record.keys()
        if missing:
            raise ReplayLoaderError(
                f"Replay record missing required fields: {sorted(missing)}"
            )

        if not isinstance(record["engine_run_id"], str):
            raise ReplayLoaderError("engine_run_id must be a string")

        if not isinstance(record["decision_envelope"], dict):
            raise ReplayLoaderError("decision_envelope must be a dict")

        if not isinstance(record["firewall_result"], dict):
            raise ReplayLoaderError("firewall_result must be a dict")

        if not isinstance(record["execution_result"], dict):
            raise ReplayLoaderError("execution_result must be a dict")

        if not isinstance(record["metadata"], dict):
            raise ReplayLoaderError("metadata must be a dict")

    def load(self, engine_run_id: str) -> Dict[str, Any]:
        if not engine_run_id:
            raise ReplayLoaderError("engine_run_id is required")

        with open(self.replay_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("engine_run_id") == engine_run_id:
                    self._validate_record(record)
                    return record

        raise ReplayLoaderError(
            f"No replay record found for engine_run_id={engine_run_id}"
        )

    def group_by_run(self) -> Dict[str, Dict[str, Any]]:
        """
        Load ALL replay records indexed by engine_run_id.
        Used for forensic inspection and reporting.
        """
        results: Dict[str, Dict[str, Any]] = {}

        with open(self.replay_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                rid = record.get("engine_run_id")
                if not rid:
                    continue

                self._validate_record(record)
                results[rid] = record

        return results
