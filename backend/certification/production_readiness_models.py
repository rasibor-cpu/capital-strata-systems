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
    expires_at: str | None = None
    signature: str | None = None

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
    *,
    profile: str | None = None,
) -> AcceptanceResult:
    from backend.certification.evidence_authority import (
        evidence_rejection_reason,
        production_evidence_accepted,
        resolve_certification_profile,
    )

    resolved_profile = resolve_certification_profile(profile)
    by_area = {str(row.area).upper(): row for row in evidence}
    checks = []
    blockers = []
    passed = 0
    for requirement in requirements:
        row = by_area.get(requirement)
        accepted = bool(row and production_evidence_accepted(row, profile=resolved_profile))
        rejection = (
            evidence_rejection_reason(row, profile=resolved_profile)
            if row and resolved_profile == "production"
            else None
        )
        if accepted:
            passed += 1
        else:
            blockers.append(requirement)
        if row is None:
            status = "EVIDENCE_MISSING"
        elif accepted:
            status = "EVIDENCE_VERIFIED"
        elif rejection:
            status = f"EVIDENCE_REJECTED:{rejection}"
        else:
            status = row.status.value
        checks.append(
            {
                "requirement": requirement,
                "status": status,
                "evidence_id": row.evidence_id if row else None,
                "reference": row.reference if row else None,
                "remediation": (
                    row.remediation
                    if row and row.remediation
                    else f"Capture and independently verify {requirement.lower()} evidence."
                ),
                "certification_profile": resolved_profile,
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
