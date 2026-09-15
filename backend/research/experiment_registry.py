from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping


@dataclass(frozen=True)
class ResearchExperiment:
    experiment_id: str
    strategy_id: str
    hypothesis: str
    owner_id: str
    dataset_id: str
    parameters: tuple[tuple[str, str], ...]
    created_at_utc: datetime
    code_reference: str


@dataclass(frozen=True)
class ResearchApproval:
    approval_id: str
    experiment_id: str
    approver_id: str
    approver_role: str
    approved_at_utc: datetime
    decision: str
    rationale: str


ALLOWED_APPROVER_ROLES = {"RESEARCH_REVIEWER", "RISK_REVIEWER", "ADMIN"}
ALLOWED_DECISIONS = {"APPROVED_SHADOW", "REJECTED", "CHANGES_REQUIRED"}


def _is_utc(value: datetime) -> bool:
    return (
        value.tzinfo is not None
        and value.utcoffset() is not None
        and value.utcoffset() == timezone.utc.utcoffset(value)
    )


def create_experiment(
    *,
    experiment_id: str,
    strategy_id: str,
    hypothesis: str,
    owner_id: str,
    dataset_id: str,
    parameters: Mapping[str, object],
    created_at_utc: datetime,
    code_reference: str,
) -> ResearchExperiment:
    fields = {
        "experiment_id": experiment_id,
        "strategy_id": strategy_id,
        "hypothesis": hypothesis,
        "owner_id": owner_id,
        "dataset_id": dataset_id,
        "code_reference": code_reference,
    }
    if any(not value.strip() for value in fields.values()):
        raise ValueError("all experiment identity fields are required")
    if not _is_utc(created_at_utc):
        raise ValueError("created_at_utc must be timezone-aware UTC")

    normalized = tuple(sorted((str(k), str(v)) for k, v in parameters.items()))
    return ResearchExperiment(
        experiment_id=experiment_id,
        strategy_id=strategy_id,
        hypothesis=hypothesis,
        owner_id=owner_id,
        dataset_id=dataset_id,
        parameters=normalized,
        created_at_utc=created_at_utc,
        code_reference=code_reference,
    )


def record_research_approval(
    experiment: ResearchExperiment,
    *,
    approval_id: str,
    approver_id: str,
    approver_role: str,
    approved_at_utc: datetime,
    decision: str,
    rationale: str,
) -> ResearchApproval:
    if not approval_id.strip() or not approver_id.strip() or not rationale.strip():
        raise ValueError("approval id, approver id, and rationale are required")
    if approver_role.upper() not in ALLOWED_APPROVER_ROLES:
        raise ValueError("approver role is not authorized")
    if decision.upper() not in ALLOWED_DECISIONS:
        raise ValueError("unsupported research decision")
    if not _is_utc(approved_at_utc):
        raise ValueError("approved_at_utc must be timezone-aware UTC")
    if approved_at_utc < experiment.created_at_utc:
        raise ValueError("approval cannot predate experiment creation")

    return ResearchApproval(
        approval_id=approval_id,
        experiment_id=experiment.experiment_id,
        approver_id=approver_id,
        approver_role=approver_role.upper(),
        approved_at_utc=approved_at_utc,
        decision=decision.upper(),
        rationale=rationale,
    )


def approval_allows_shadow_research(approval: ResearchApproval | None) -> bool:
    return approval is not None and approval.decision == "APPROVED_SHADOW"


def approval_allows_live_trading(approval: ResearchApproval | None) -> bool:
    # Research approval is intentionally never execution authority.
    return False
