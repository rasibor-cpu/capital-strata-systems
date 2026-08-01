"""Phase 193 — broker qualification workflow (offline, fail-closed, hardened scores)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from backend.app.brokers.multi_broker_readiness.audit_matrix import (
    BROKER_AUDIT_MATRIX,
    get_capability_profile,
)
from backend.app.brokers.multi_broker_readiness.rc004 import evaluate_rc004_readiness
from backend.app.brokers.operational_qualification.evidence import (
    QualificationEvidence,
    build_qualification_evidence,
)
from backend.app.brokers.operational_qualification.precheck import (
    run_operational_qualification_precheck,
)
from backend.app.brokers.operational_qualification.scoring import (
    SCORE_FORMULA_VERSION,
    build_state_evidence_flags,
    compute_hardened_scores,
)
from backend.app.brokers.operational_qualification.states import QualificationStateMachine
from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository
from backend.app.governance.enterprise_certification_registry.seed import seed_phase_registry

FRAMEWORK_VERSION = "193.2"
SCHEMA_VERSION = "193.2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class OperationalQualificationResult:
    broker: str
    stage: str
    readiness_score: int
    implementation_maturity_score: int
    operational_readiness_score: int
    aggregate_qualification_score: int
    readiness_label: str
    evidence: QualificationEvidence
    precheck_status: str
    transitions: tuple[dict[str, object], ...]
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "stage": self.stage,
            "readiness_score": self.aggregate_qualification_score,
            "implementation_maturity_score": self.implementation_maturity_score,
            "operational_readiness_score": self.operational_readiness_score,
            "aggregate_qualification_score": self.aggregate_qualification_score,
            "readiness_label": self.readiness_label,
            "precheck_status": self.precheck_status,
            "transitions": list(self.transitions),
            "execution_authority": False,
            "evidence": self.evidence.as_dict(),
            "framework_version": FRAMEWORK_VERSION,
            "schema_version": SCHEMA_VERSION,
            "score_formula_version": SCORE_FORMULA_VERSION,
        }

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("qualification result must not grant execution_authority")
        if self.readiness_score != self.aggregate_qualification_score:
            raise ValueError("readiness_score must equal aggregate_qualification_score")


def qualify_broker(
    broker: str,
    env: Mapping[str, Any] | None = None,
    *,
    asset_class: str = "",
    repository: RegistryRepository | None = None,
    timestamp: str | None = None,
    qualification_id: str | None = None,
    expected_schema_version: str = "189.1",
    expected_provider_name: str = "",
    expected_provider_version: str = "",
    expected_min_generation: int = 1,
    repo_root: Any = None,
    authenticated_online: bool = False,
) -> OperationalQualificationResult:
    """Run offline operational qualification. Never authenticates or contacts brokers.

    ``authenticated_online`` defaults False and must stay False for Phase 193
    (no broker contact). It exists only so future phases can flip the gate without
    letting scores alone advance state.
    """
    broker_key = str(broker or "").upper()
    repo = repository if repository is not None else seed_phase_registry()
    ts = timestamp or _utc_now()
    qid = qualification_id or f"oq-{broker_key.lower()}-{uuid4().hex[:12]}"

    # Phase 193 hard rule: never treat runs as authenticated online.
    authenticated_online = False

    precheck = run_operational_qualification_precheck(
        broker_key,
        env,
        asset_class=asset_class,
        repository=repo,
        expected_schema_version=expected_schema_version,
        expected_provider_name=expected_provider_name,
        expected_provider_version=expected_provider_version,
        expected_min_generation=expected_min_generation,
        repo_root=repo_root,
    )

    audit = BROKER_AUDIT_MATRIX.get(broker_key, {})
    profile = get_capability_profile(broker_key)
    rc004 = evaluate_rc004_readiness(broker_key, repo_root=repo_root)

    impl_cap = str(audit.get("implementation_status", "NOT_STARTED"))
    configured = (
        "READY"
        if precheck.credentials_configured and precheck.endpoint_configured
        else (
            "PARTIAL"
            if precheck.endpoint_configured or precheck.credentials_configured
            else "NOT_CONFIGURED"
        )
    )

    hard_blocked = precheck.status == "BLOCKED" or any(
        b.startswith("broker_blocked:")
        or b.startswith("registry_claim_invalid:")
        or b == "stale_registry_generation"
        or b.startswith("provider_fingerprint_mismatch")
        for b in precheck.blockers
    )

    scores = compute_hardened_scores(
        implementation_status=impl_cap,
        audit_classification=str(audit.get("classification", "NOT_STARTED")),
        capability_profile_ok=precheck.capability_profile_ok,
        provider_compatible=precheck.provider_compatible,
        certification_readiness=bool(audit.get("certification_readiness")),
        registry_entry_ok=precheck.registry_entry_ok,
        schema_compatible=precheck.schema_compatible,
        governance_aligned=precheck.governance_aligned,
        rc004_live_denied=precheck.rc004_live_denied,
        authorization_ttl_classified=precheck.authorization_ttl_classified,
        credentials_configured=precheck.credentials_configured,
        endpoint_configured=precheck.endpoint_configured,
        configured_readiness=configured,
        authenticated_online=authenticated_online,
    )

    evidence_flags = build_state_evidence_flags(
        registry_entry_ok=precheck.registry_entry_ok,
        capability_profile_ok=precheck.capability_profile_ok,
        schema_compatible=precheck.schema_compatible,
        rc004_live_denied=precheck.rc004_live_denied,
        authorization_ttl_classified=precheck.authorization_ttl_classified,
        provider_compatible=precheck.provider_compatible,
        hard_blocked=hard_blocked,
        endpoint_configured=precheck.endpoint_configured,
        credentials_configured=precheck.credentials_configured,
        authenticated_online=authenticated_online,
        certification_readiness=bool(audit.get("certification_readiness")),
    )

    machine = QualificationStateMachine()
    stage, history = machine.run_to_completion(
        evidence_flags,
        blocked=hard_blocked,
        reason=";".join(precheck.blockers[:3]) if hard_blocked else "",
    )

    # NOT_READY may never be QUALIFIED or READ_ONLY_READY.
    ro_qual = "NOT_READY"
    if stage in {"READ_ONLY_READY", "QUALIFIED"} and authenticated_online:
        ro_qual = stage
    elif stage in {"READ_ONLY_READY", "QUALIFIED"} and not authenticated_online:
        # Defensive: force stage back — scores/labels cannot unlock RO/QUALIFIED offline.
        stage = "AUTH_READY" if precheck.credentials_configured else (
            "CONFIG_READY" if precheck.endpoint_configured else "NOT_STARTED"
        )
        ro_qual = "NOT_READY"

    registry_generation = int(precheck.diagnostics.get("registry_generation", 0) or 0)
    provider_name = str(
        precheck.diagnostics.get("registry_provider_name") or audit.get("connectivity") or ""
    )
    provider_version = str(precheck.diagnostics.get("registry_provider_version") or "")

    evidence = build_qualification_evidence(
        qualification_id=qid,
        broker=broker_key,
        asset_class=precheck.asset_class or asset_class or "",
        provider_name=provider_name,
        provider_version=provider_version,
        schema_version=SCHEMA_VERSION,
        capability_profile=profile.as_dict(),
        registry_generation=registry_generation,
        rc004_posture=rc004.status,
        qualification_stage=stage,
        implementation_maturity_score=scores.implementation_maturity_score,
        operational_readiness_score=scores.operational_readiness_score,
        aggregate_qualification_score=scores.aggregate_qualification_score,
        readiness_label=scores.readiness_label,
        mandatory_gate_results=scores.mandatory_gate_results.as_dict(),
        blocker_list=precheck.blockers,
        generated_timestamp=ts,
        score_formula_version=SCORE_FORMULA_VERSION,
        implementation_capability=impl_cap,
        configured_readiness=configured,
        read_only_qualification=ro_qual,
        authorization_ttl_status=str(precheck.diagnostics.get("authorization_ttl_status", "N/A")),
        diagnostics={
            "redacted": True,
            "secret_values_captured": False,
            "authentication_performed": False,
            "network_contact_performed": False,
            "read_only_ttl_is_not_live_authority": True,
            "precheck_status": precheck.status,
            "score_formula_version": SCORE_FORMULA_VERSION,
            "score_alone_cannot_advance_state": True,
            "uncapped_operational_readiness_score": scores.uncapped_operational_readiness_score,
            "uncapped_aggregate_qualification_score": scores.uncapped_aggregate_qualification_score,
            "state_evidence_flags": evidence_flags,
        },
    )

    return OperationalQualificationResult(
        broker=broker_key,
        stage=stage,
        readiness_score=scores.aggregate_qualification_score,
        implementation_maturity_score=scores.implementation_maturity_score,
        operational_readiness_score=scores.operational_readiness_score,
        aggregate_qualification_score=scores.aggregate_qualification_score,
        readiness_label=scores.readiness_label,
        evidence=evidence,
        precheck_status=precheck.status,
        transitions=tuple(t.as_dict() for t in history),
        execution_authority=False,
    )
