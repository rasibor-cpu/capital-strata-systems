"""Pre-rotation impact analysis over the ESMS-002 dependency graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.security.credential_dependency_map import CredentialDependencyMap


@dataclass(frozen=True)
class RotationImpact:
    vcid: str
    affected_services: tuple[str, ...]
    estimated_downtime_seconds: int
    safe_rotation: bool
    blocked_rotation: bool
    rollback_available: bool
    blockers: tuple[str, ...]
    execution_allowed: bool = False


def analyze_rotation(
    vcid: str,
    dependencies: CredentialDependencyMap,
    *,
    maintenance_window: bool = False,
) -> RotationImpact:
    rows = dependencies.consumers(vcid)
    blockers = tuple(
        row.consumer for row in rows if row.required and not row.safe_to_pause and not maintenance_window
    )
    rollback = bool(rows) and all(row.rollback_supported for row in rows)
    blocked = bool(blockers)
    return RotationImpact(
        vcid=vcid,
        affected_services=tuple(sorted(row.consumer for row in rows)),
        estimated_downtime_seconds=0 if not rows else 15 * len(rows),
        safe_rotation=not blocked and (rollback or not rows),
        blocked_rotation=blocked,
        rollback_available=rollback,
        blockers=blockers,
    )


def impact_payload(impact: RotationImpact) -> dict:
    return asdict(impact)


__all__ = ["RotationImpact", "analyze_rotation", "impact_payload"]
