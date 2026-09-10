from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_runtime_health_snapshot(
    state_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read existing runtime state without changing or treating it as authority."""
    path = Path(state_path) if state_path else Path(__file__).resolve().parents[2] / "runtime_supervisor.json"
    snapshot: dict[str, Any] = {
        "process_alive": True,
        "api_health": "HEALTHY",
        "evidence_refs": ["runtime_health_provider.current_process"],
    }
    try:
        with path.open("r", encoding="utf-8") as handle:
            persisted = json.load(handle)
        if not isinstance(persisted, dict):
            raise ValueError("runtime state must be an object")
    except (OSError, ValueError, json.JSONDecodeError):
        snapshot["state_reason_codes"] = ["RUNTIME_STATE_UNAVAILABLE"]
        snapshot["evidence_refs"].append("runtime_health_provider.state_unavailable")
        return snapshot

    snapshot.update(
        {
            "runtime_state_file_present": True,
            "runtime_pid": os.getpid(),
            "runtime_start_time": persisted.get("start_time"),
            "uptime_seconds": persisted.get("uptime_seconds"),
            "cycles_completed": persisted.get("cycles_completed"),
            "runtime_errors": persisted.get("runtime_errors"),
            "broker_disconnects": persisted.get("broker_disconnects"),
            "recovery_attempts": persisted.get("recovery_attempts"),
            "alerts_generated": persisted.get("alerts_generated"),
            "evidence_refs": [
                "runtime_health_provider.current_process",
                "runtime_supervisor.json.read_only",
            ],
        }
    )
    return snapshot


__all__ = ["read_runtime_health_snapshot"]