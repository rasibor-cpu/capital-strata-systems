from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping


_ALLOWED_HEALTH = {"HEALTHY", "DEGRADED", "UNAVAILABLE", "UNKNOWN"}
_ALLOWED_CONTROL = {"PASS", "WARN", "FAIL", "UNKNOWN"}


def _is_utc(value: datetime) -> bool:
    return (
        value.tzinfo is not None
        and value.utcoffset() is not None
        and value.utcoffset() == timezone.utc.utcoffset(value)
    )


@dataclass(frozen=True)
class ExecutiveCommandInput:
    observed_at_utc: datetime
    runtime_health: str
    broker_health: str
    data_freshness: str
    governance_status: str
    security_status: str
    reconciliation_status: str
    backup_status: str
    recovery_status: str
    capacity_status: str
    open_critical_incidents: int = 0
    open_high_incidents: int = 0


@dataclass(frozen=True)
class ExecutiveCommandSnapshot:
    observed_at_utc: datetime
    operating_posture: str
    attention_level: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    dimensions: Mapping[str, str]
    execution_allowed: bool = False
    broker_execution_armed: bool = False
    money_movement_authorized: bool = False
    live_trading_authorized: bool = False


def build_executive_command_snapshot(data: ExecutiveCommandInput) -> ExecutiveCommandSnapshot:
    """Build a deterministic, read-only executive operations posture.

    This aggregation layer summarizes already-normalized operational dimensions.
    It never grants trading, broker, or money-movement authority.
    """

    if not _is_utc(data.observed_at_utc):
        raise ValueError("observed_at_utc must be timezone-aware UTC")
    if data.open_critical_incidents < 0 or data.open_high_incidents < 0:
        raise ValueError("incident counts must be non-negative")

    health_dimensions = {
        "runtime_health": data.runtime_health.upper(),
        "broker_health": data.broker_health.upper(),
        "data_freshness": data.data_freshness.upper(),
    }
    control_dimensions = {
        "governance_status": data.governance_status.upper(),
        "security_status": data.security_status.upper(),
        "reconciliation_status": data.reconciliation_status.upper(),
        "backup_status": data.backup_status.upper(),
        "recovery_status": data.recovery_status.upper(),
        "capacity_status": data.capacity_status.upper(),
    }

    invalid = [
        name for name, value in health_dimensions.items() if value not in _ALLOWED_HEALTH
    ] + [
        name for name, value in control_dimensions.items() if value not in _ALLOWED_CONTROL
    ]
    if invalid:
        raise ValueError(f"unsupported executive-command status fields: {', '.join(sorted(invalid))}")

    blockers: list[str] = []
    warnings: list[str] = []

    if health_dimensions["runtime_health"] in {"UNAVAILABLE", "UNKNOWN"}:
        blockers.append("RUNTIME_HEALTH_UNAVAILABLE")
    elif health_dimensions["runtime_health"] == "DEGRADED":
        warnings.append("RUNTIME_HEALTH_DEGRADED")

    if health_dimensions["broker_health"] in {"UNAVAILABLE", "UNKNOWN"}:
        blockers.append("BROKER_HEALTH_UNAVAILABLE")
    elif health_dimensions["broker_health"] == "DEGRADED":
        warnings.append("BROKER_HEALTH_DEGRADED")

    if health_dimensions["data_freshness"] in {"UNAVAILABLE", "UNKNOWN"}:
        blockers.append("DATA_FRESHNESS_UNAVAILABLE")
    elif health_dimensions["data_freshness"] == "DEGRADED":
        warnings.append("DATA_FRESHNESS_DEGRADED")

    for name, value in control_dimensions.items():
        code = name.upper()
        if value in {"FAIL", "UNKNOWN"}:
            blockers.append(f"{code}_{value}")
        elif value == "WARN":
            warnings.append(f"{code}_WARN")

    if data.open_critical_incidents:
        blockers.append("CRITICAL_INCIDENT_OPEN")
    if data.open_high_incidents:
        warnings.append("HIGH_INCIDENT_OPEN")

    if blockers:
        operating_posture = "BLOCKED"
        attention_level = "CRITICAL"
    elif warnings:
        operating_posture = "DEGRADED"
        attention_level = "HIGH"
    else:
        operating_posture = "STABLE"
        attention_level = "NORMAL"

    dimensions = {**health_dimensions, **control_dimensions}

    return ExecutiveCommandSnapshot(
        observed_at_utc=data.observed_at_utc,
        operating_posture=operating_posture,
        attention_level=attention_level,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
        dimensions=dimensions,
    )
