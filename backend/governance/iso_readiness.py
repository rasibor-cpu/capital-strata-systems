"""Evidence-backed ISO readiness assessments; never certification claims."""

from __future__ import annotations

from typing import Iterable

from backend.governance.governance_models import (
    EvidenceStatus,
    GovernanceEvidence,
    ReadinessResult,
)

ISO_27001_CONTROLS = (
    "ACCESS_CONTROL",
    "ASSET_INVENTORY",
    "CRYPTOGRAPHY",
    "LOGGING",
    "AUDIT",
    "BACKUP",
    "RECOVERY",
    "SECURE_DEVELOPMENT",
    "CHANGE_CONTROL",
    "SUPPLIER_MANAGEMENT",
    "VULNERABILITY_MANAGEMENT",
    "INCIDENT_RESPONSE",
)

ISO_9001_CONTROLS = (
    "PROCESS_OWNERSHIP",
    "DOCUMENTATION",
    "CHANGE_HISTORY",
    "VERIFICATION_EVIDENCE",
    "CONTINUOUS_IMPROVEMENT",
    "OPERATIONAL_KPIS",
    "CORRECTIVE_ACTIONS",
    "PREVENTIVE_ACTIONS",
)


def assess_iso_27001(evidence: Iterable[GovernanceEvidence]) -> ReadinessResult:
    return _assess("ISO_27001_READINESS", ISO_27001_CONTROLS, evidence)


def assess_iso_9001(evidence: Iterable[GovernanceEvidence]) -> ReadinessResult:
    return _assess("ISO_9001_READINESS", ISO_9001_CONTROLS, evidence)


def _assess(
    framework: str,
    controls: tuple[str, ...],
    evidence: Iterable[GovernanceEvidence],
) -> ReadinessResult:
    rows = list(evidence)
    by_control: dict[str, list[GovernanceEvidence]] = {}
    for row in rows:
        by_control.setdefault(_normalize(row.control), []).append(row)
    output = []
    satisfied = 0
    failed = 0
    blockers = []
    for control in controls:
        candidates = by_control.get(control, [])
        verified = next(
            (
                row
                for row in candidates
                if row.status is EvidenceStatus.PRESENT and row.verified
            ),
            None,
        )
        failure = next(
            (row for row in candidates if row.status is EvidenceStatus.FAILED),
            None,
        )
        if verified is not None:
            satisfied += 1
            output.append(
                {
                    "control": control,
                    "status": "EVIDENCE_VERIFIED",
                    "evidence_id": verified.evidence_id,
                    "reference": verified.reference,
                    "source": verified.source,
                }
            )
        elif failure is not None:
            failed += 1
            blockers.append(control)
            output.append(
                {
                    "control": control,
                    "status": "EVIDENCE_FAILED",
                    "evidence_id": failure.evidence_id,
                    "reference": failure.reference,
                    "source": failure.source,
                }
            )
        else:
            blockers.append(control)
            output.append(
                {
                    "control": control,
                    "status": "EVIDENCE_MISSING",
                    "evidence_id": None,
                    "reference": None,
                    "source": None,
                }
            )
    total = len(controls)
    return ReadinessResult(
        framework=framework,
        percentage=round(100.0 * satisfied / total, 2) if total else 0.0,
        controls_total=total,
        controls_satisfied=satisfied,
        controls_missing=total - satisfied - failed,
        controls_failed=failed,
        evidence=tuple(output),
        blockers=tuple(blockers),
        formal_certification_claimed=False,
    )


def _normalize(value: str) -> str:
    return "_".join(str(value or "").strip().upper().replace("-", " ").split())


__all__ = [
    "ISO_27001_CONTROLS",
    "ISO_9001_CONTROLS",
    "assess_iso_27001",
    "assess_iso_9001",
]
