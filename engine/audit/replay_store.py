"""
Replay Store – Append-Only Forensic Persistence
-----------------------------------------------

Purpose:
- Persist a full, immutable execution record keyed by ENGINE_RUN_ID
- Enable deterministic replay and post-mortem analysis
- Enforce append-only semantics (no overwrite, no mutation)

Storage:
- JSON Lines (JSONL)
- One record per ENGINE_RUN_ID
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any


class ReplayStoreError(RuntimeError):
    pass


class ReplayStore:
    def __init__(self, base_dir: str = "audit_logs"):
        self.base_dir = base_dir
        self.replay_path = os.path.join(self.base_dir, "replays.jsonl")
        os.makedirs(self.base_dir, exist_ok=True)

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _existing_run_ids(self) -> set[str]:
        if not os.path.exists(self.replay_path):
            return set()

        run_ids = set()
        with open(self.replay_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    rid = obj.get("engine_run_id")
                    if rid:
                        run_ids.add(rid)
                except json.JSONDecodeError:
                    continue
        return run_ids

    def persist(
        self,
        *,
        engine_run_id: str,
        decision_envelope: Dict[str, Any],
        firewall_result: Dict[str, Any],
        execution_result: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        if not engine_run_id:
            raise ReplayStoreError("engine_run_id is required")

        existing = self._existing_run_ids()
        if engine_run_id in existing:
            raise ReplayStoreError(
                f"Replay record already exists for engine_run_id={engine_run_id}"
            )

        record = {
            "engine_run_id": engine_run_id,
            "stored_at_utc": self._now_utc(),
            "decision_envelope": decision_envelope,
            "firewall_result": firewall_result,
            "execution_result": execution_result,
            "metadata": metadata or {},
        }

        try:
            with open(self.replay_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")
        except Exception as e:
            raise ReplayStoreError(f"Failed to persist replay record: {e}") from e
