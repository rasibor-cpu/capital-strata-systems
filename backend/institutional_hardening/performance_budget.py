from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceBudget:
    dashboard_snapshot_ms: float = 100.0
    websocket_delta_ms: float = 50.0
    replay_load_ms: float = 500.0
    mobile_view_ms: float = 250.0
    payload_bytes: int = 65536


def assess_performance_budget(*, metric: str, elapsed_ms: float, payload_bytes: int, budget: PerformanceBudget | None = None) -> dict:
    active = budget or PerformanceBudget()
    thresholds = {
        "dashboard_snapshot": active.dashboard_snapshot_ms,
        "websocket_delta": active.websocket_delta_ms,
        "replay_load": active.replay_load_ms,
        "mobile_view": active.mobile_view_ms,
    }
    if metric not in thresholds:
        raise ValueError("unknown performance metric")
    time_ok = elapsed_ms <= thresholds[metric]
    size_ok = payload_bytes <= active.payload_bytes
    return {
        "metric": metric,
        "elapsed_ms": elapsed_ms,
        "payload_bytes": payload_bytes,
        "time_budget_ms": thresholds[metric],
        "payload_budget_bytes": active.payload_bytes,
        "status": "PASS" if time_ok and size_ok else "BUDGET_EXCEEDED",
        "stale_state_warning": not time_ok,
    }
