from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LiveReadinessReport:
    readiness_status: str
    failed_checks: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics_summary: dict[str, Any]
    operational_summary: dict[str, Any]
    recommendation: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
