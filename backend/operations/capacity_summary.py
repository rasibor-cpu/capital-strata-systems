from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CapacityTelemetry:
    cpu_utilization_pct: Decimal
    memory_utilization_pct: Decimal
    dashboard_latency_ms: Decimal
    payload_bytes: int
    websocket_latency_ms: Decimal


@dataclass(frozen=True)
class CapacitySummary:
    status: str
    warnings: tuple[str, ...]
    metrics: dict[str, str | int]


def _pct(value: Decimal, name: str) -> None:
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be in [0, 100]")


def build_capacity_summary(
    telemetry: CapacityTelemetry,
    *,
    cpu_warn_pct: Decimal = Decimal("80"),
    memory_warn_pct: Decimal = Decimal("85"),
    dashboard_warn_ms: Decimal = Decimal("250"),
    websocket_warn_ms: Decimal = Decimal("100"),
    payload_warn_bytes: int = 131072,
) -> CapacitySummary:
    _pct(telemetry.cpu_utilization_pct, "cpu_utilization_pct")
    _pct(telemetry.memory_utilization_pct, "memory_utilization_pct")
    if telemetry.dashboard_latency_ms < 0 or telemetry.websocket_latency_ms < 0:
        raise ValueError("latency must be non-negative")
    if telemetry.payload_bytes < 0:
        raise ValueError("payload_bytes must be non-negative")

    warnings: list[str] = []
    if telemetry.cpu_utilization_pct >= cpu_warn_pct:
        warnings.append("CPU_CAPACITY_WARN")
    if telemetry.memory_utilization_pct >= memory_warn_pct:
        warnings.append("MEMORY_CAPACITY_WARN")
    if telemetry.dashboard_latency_ms >= dashboard_warn_ms:
        warnings.append("DASHBOARD_LATENCY_WARN")
    if telemetry.websocket_latency_ms >= websocket_warn_ms:
        warnings.append("WEBSOCKET_LATENCY_WARN")
    if telemetry.payload_bytes >= payload_warn_bytes:
        warnings.append("PAYLOAD_SIZE_WARN")

    return CapacitySummary(
        status="WARN" if warnings else "PASS",
        warnings=tuple(sorted(warnings)),
        metrics={
            "cpu_utilization_pct": format(telemetry.cpu_utilization_pct, "f"),
            "memory_utilization_pct": format(telemetry.memory_utilization_pct, "f"),
            "dashboard_latency_ms": format(telemetry.dashboard_latency_ms, "f"),
            "websocket_latency_ms": format(telemetry.websocket_latency_ms, "f"),
            "payload_bytes": telemetry.payload_bytes,
        },
    )
