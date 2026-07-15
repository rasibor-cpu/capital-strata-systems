from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider


def build_runtime_snapshot(source: Callable[[], Mapping[str, Any] | None] | None = None) -> dict[str, Any]:
    return RuntimeSnapshotProvider(source).get_snapshot()


def runtime_snapshot_state_provider(source: Callable[[], Mapping[str, Any] | None] | None = None):
    def provider() -> dict[str, Any]:
        return RuntimeSnapshotProvider(source, active_source_binding=True).get_state_payload()

    return provider


__all__ = ["build_runtime_snapshot", "runtime_snapshot_state_provider"]
