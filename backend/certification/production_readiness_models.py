"""Evidence-only Phase 181 production-readiness contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class AcceptanceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_TESTED = "NOT_TESTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class CertificationEvidence:
    evidence_id: str
    area: str
    status: AcceptanceStatus
    reference: str | None
    observed_at: str | None
    source: str
    remediation: str
    verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["synthetic_claim"] = False
        payload["execution_allowed"] = False
        return payload


@dataclass(frozen=True)
class AcceptanceResult:
    framework: str
    status: str
    percentage: float
    checks: tuple[dict[str, Any], ...]
    blockers: tuple[str, ...]
    evidence_complete: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "certification_claimed": False,
            "execution_allowed": False,
        }


def evaluate_required_evidence(
    framework: str,
    requirements: tuple[str, ...],
    evidence: list[CertificationEvidence] | tuple[CertificationEvidence, ...],
) -> AcceptanceResult:
    by_area = {str(row.area).upper(): row for row in evidence}
    checks = []
    blockers = []
    passed = 0
    for requirement in requirements:
        row = by_area.get(requirement)
        accepted = bool(
            row
            and row.status is AcceptanceStatus.PASS
            and row.verified
            and row.reference
            and row.observed_at
        )
        if accepted:
            passed += 1
        else:
            blockers.append(requirement)
        checks.append(
            {
                "requirement": requirement,
                "status": "EVIDENCE_VERIFIED" if accepted else (
                    row.status.value if row else "EVIDENCE_MISSING"
                ),
                "evidence_id": row.evidence_id if row else None,
                "reference": row.reference if row else None,
                "remediation": (
                    row.remediation
                    if row and row.remediation
                    else f"Capture and independently verify {requirement.lower()} evidence."
                ),
            }
        )
    total = len(requirements)
    return AcceptanceResult(
        framework=framework,
        status="EVIDENCE_COMPLETE" if passed == total else "EVIDENCE_INCOMPLETE",
        percentage=round(100.0 * passed / total, 2) if total else 0.0,
        checks=tuple(checks),
        blockers=tuple(blockers),
        evidence_complete=passed == total,
    )


__all__ = [
    "AcceptanceResult",
    "AcceptanceStatus",
    "CertificationEvidence",
    "evaluate_required_evidence",
]
