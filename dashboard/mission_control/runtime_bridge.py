from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider


def build_runtime_snapshot(source: Callable[[], Mapping[str, Any] | None] | None = None) -> dict[str, Any]:
    return RuntimeSnapshotProvider(source).get_snapshot()


def runtime_snapshot_state_provider(source: Callable[[], Mapping[str, Any] | None] | None = None):
    def provider() -> dict[str, Any]:
        snapshot = RuntimeSnapshotProvider(source).get_snapshot()
        return {
            "runtime_snapshot": snapshot,
            "frontend_payload": source() if source is not None else None,
        }

    return provider


__all__ = ["build_runtime_snapshot", "runtime_snapshot_state_provider"]
