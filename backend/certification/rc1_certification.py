"""Evidence-only CSS Enterprise RC1 certification closure."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

RC1_REQUIREMENTS = (
    "RUNTIME",
    "IDENTITY",
    "SECRET_RUNTIME",
    "OAUTH_RUNTIME",
    "BROKER_RUNTIME",
    "GOVERNANCE",
    "MISSION_CONTROL",
    "REPORTS_CENTER",
    "OPTIONS_INCOME_RUNTIME",
)

COMMAND_REQUIREMENTS = ("POWERSHELL", "PYTHON", "PYTEST", "COMPILEALL", "GIT")

OWNERS = {
    "RUNTIME": "Platform Operations",
    "IDENTITY": "Identity and Access Management",
    "SECRET_RUNTIME": "Security Engineering",
    "OAUTH_RUNTIME": "Identity and Access Management",
    "BROKER_RUNTIME": "Broker Platform",
    "GOVERNANCE": "Enterprise Governance",
    "MISSION_CONTROL": "Platform Operations",
    "REPORTS_CENTER": "Enterprise Reporting",
    "OPTIONS_INCOME_RUNTIME": "Options Platform",
}


@dataclass(frozen=True)
class RC1Evidence:
    evidence_id: str
    area: str
    status: str
    reference: str | None
    observed_at: str | None
    verified: bool
    command: str | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    output_reference: str | None = None

    def accepted(self) -> bool:
        return bool(
            self.status.upper() == "PASS"
            and self.verified
            and self.reference
            and self.observed_at
        )

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "result_fabricated": False}


@dataclass(frozen=True)
class RC1Blocker:
    blocker_id: str
    description: str
    severity: str
    owner: str
    remediation: str
    evidence: str | None
    verification_status: str

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def certify_rc1(
    evidence: list[RC1Evidence] | tuple[RC1Evidence, ...],
    *,
    additional_blockers: list[RC1Blocker] | tuple[RC1Blocker, ...] = (),
) -> dict[str, Any]:
    supplied = tuple(evidence)
    by_area = _group_by_area(supplied)
    requirement_status = {
        area: _accepted(by_area.get(area, ())) for area in RC1_REQUIREMENTS
    }
    command_status = {
        area: _command_accepted(by_area.get(area, ())) for area in COMMAND_REQUIREMENTS
    }
    blockers = _automatic_blockers(requirement_status, command_status, by_area)
    blockers.extend(additional_blockers)
    blockers = sorted(blockers, key=lambda row: row.blocker_id)
    gates_pass = all(requirement_status.values()) and all(command_status.values())
    if not gates_pass or any(row.severity == "CRITICAL" for row in blockers):
        status = "NOT_READY"
    elif blockers:
        status = "READY_WITH_BLOCKERS"
    else:
        status = "CERTIFIED"
    scores = _scorecard(requirement_status, command_status)
    return {
        "schema_version": "css.enterprise.rc1.certification.v1",
        "status": status,
        "scorecard": scores,
        "requirements": requirement_status,
        "command_runner": command_status,
        "outstanding_blockers": [row.as_dict() for row in blockers],
        "evidence_inventory": [row.as_dict() for row in supplied],
        "evidence_complete": gates_pass,
        "evidence_fabricated": False,
        "tag_recommendation": "CSS_ENTERPRISE_RC1" if status == "CERTIFIED" else None,
        "tag_creation_authorized": False,
        "deployment_authorized": False,
        "production_trading_certified": False,
        "execution_posture": "DISABLED",
        "execution_authority": "BLOCKED",
        "fail_closed": True,
        "advisory_only": True,
        "execution_allowed": False,
    }


def _group_by_area(evidence: tuple[RC1Evidence, ...]) -> dict[str, tuple[RC1Evidence, ...]]:
    grouped: dict[str, list[RC1Evidence]] = {}
    for row in evidence:
        grouped.setdefault(row.area.upper(), []).append(row)
    return {area: tuple(rows) for area, rows in grouped.items()}


def _accepted(rows: tuple[RC1Evidence, ...]) -> bool:
    return any(row.accepted() for row in rows) and not any(
        row.verified and row.status.upper() == "FAIL" for row in rows
    )


def _command_accepted(rows: tuple[RC1Evidence, ...]) -> bool:
    return _accepted(rows) and any(
        row.accepted()
        and row.command
        and row.exit_code == 0
        and row.duration_seconds is not None
        and row.output_reference
        for row in rows
    )


def _automatic_blockers(
    requirements: Mapping[str, bool],
    commands: Mapping[str, bool],
    evidence: Mapping[str, tuple[RC1Evidence, ...]],
) -> list[RC1Blocker]:
    blockers = []
    for area, passed in commands.items():
        if passed:
            continue
        rows = evidence.get(area, ())
        blockers.append(
            RC1Blocker(
                blocker_id=f"RC1-CMD-{area}",
                description=f"{area} command execution lacks verified output, exit code, and duration.",
                severity="CRITICAL",
                owner="Platform Operations",
                remediation=(
                    "Restore the command execution environment and rerun the command, "
                    "capturing stdout, stderr, exit code, and duration."
                ),
                evidence=rows[-1].reference if rows else None,
                verification_status="FAILED" if rows else "NOT_VERIFIED",
            )
        )
    for area, passed in requirements.items():
        if passed:
            continue
        rows = evidence.get(area, ())
        blockers.append(
            RC1Blocker(
                blocker_id=f"RC1-GATE-{area}",
                description=f"{area} readiness lacks accepted RC1 evidence.",
                severity="HIGH",
                owner=OWNERS[area],
                remediation=f"Produce and independently verify the {area.lower()} RC1 evidence package.",
                evidence=rows[-1].reference if rows else None,
                verification_status="FAILED" if rows else "NOT_VERIFIED",
            )
        )
    return blockers


def _scorecard(
    requirements: Mapping[str, bool],
    commands: Mapping[str, bool],
) -> dict[str, float]:
    score = lambda areas: round(
        100.0 * sum(bool(requirements.get(area)) for area in areas) / len(areas),
        2,
    )
    return {
        "runtime_readiness": score(("RUNTIME", "OPTIONS_INCOME_RUNTIME")),
        "governance_readiness": score(("GOVERNANCE",)),
        "broker_readiness": score(("BROKER_RUNTIME",)),
        "security_readiness": score(("SECRET_RUNTIME", "OAUTH_RUNTIME")),
        "identity_readiness": score(("IDENTITY",)),
        "reporting_readiness": score(("MISSION_CONTROL", "REPORTS_CENTER")),
        "certification_readiness": round(
            100.0
            * (
                sum(requirements.values())
                + sum(commands.values())
            )
            / (len(requirements) + len(commands)),
            2,
        ),
    }


__all__ = [
    "COMMAND_REQUIREMENTS",
    "RC1Blocker",
    "RC1Evidence",
    "RC1_REQUIREMENTS",
    "certify_rc1",
]
