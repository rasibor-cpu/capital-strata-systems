from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .marathon_checklist import MarathonChecklist


@dataclass(frozen=True)
class MarathonReadinessReport:
    overall_status: str
    checks_passed: tuple[str, ...]
    checks_failed: tuple[str, ...]
    warnings: tuple[str, ...]
    recommendations: tuple[str, ...]
    go_no_go: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_marathon_readiness_report(checklist: MarathonChecklist) -> MarathonReadinessReport:
    if not isinstance(checklist, MarathonChecklist):
        raise TypeError("checklist must be a MarathonChecklist")

    go_no_go = "GO" if checklist.go_no_go() else "NO_GO"
    overall_status = go_no_go

    return MarathonReadinessReport(
        overall_status=overall_status,
        checks_passed=tuple(checklist.passed_checks()),
        checks_failed=tuple(checklist.failed_checks()),
        warnings=tuple(checklist.warnings()),
        recommendations=tuple(checklist.recommendations()),
        go_no_go=go_no_go,
    )
