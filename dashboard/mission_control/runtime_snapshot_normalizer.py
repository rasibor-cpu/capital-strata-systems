from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.runtime.canonical_runtime_snapshot import (
    build_canonical_runtime_snapshot,
    offline_runtime_snapshot,
)


def normalize_runtime_snapshot(
    source: Any,
    frontend_payload: Mapping[str, Any] | None = None,
    *,
    source_name: str = "runtime_snapshot_provider",
    stale_after_seconds: float = 120.0,
) -> dict[str, Any]:
    """Compatibility wrapper for the OP-002 canonical runtime snapshot owner."""

    return build_canonical_runtime_snapshot(
        source,
        frontend_payload,
        source_name=source_name,
        stale_after_seconds=stale_after_seconds,
    )


__all__ = ["normalize_runtime_snapshot", "offline_runtime_snapshot"]
