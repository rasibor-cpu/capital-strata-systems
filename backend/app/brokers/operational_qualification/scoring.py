"""Phase 193 — hardened readiness scoring (offline, fail-closed).

SCORE_FORMULA_VERSION 193.2-hardened

Scores never grant execution authority and never alone advance state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

SCORE_FORMULA_VERSION = "193.2-hardened"

# Aggregate label bands (inclusive ranges).
_LABEL_BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 24, "BLOCKED"),
    (25, 49, "FOUNDATION_ONLY"),
    (50, 69, "PARTIAL"),
    (70, 84, "PRECHECK_READY"),
    (85, 99, "READ_ONLY_READY"),
    (100, 100, "QUALIFIED"),
)


def readiness_label_for_score(aggregate: int) -> str:
    score = max(0, min(100, int(aggregate)))
    for low, high, label in _LABEL_BANDS:
        if low <= score <= high:
            return label
    return "BLOCKED"


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(value)))


@dataclass(frozen=True)
class MandatoryGateResults:
    registry_valid: bool
    configuration_present: bool
    credentials_present: bool
    authenticated_online: bool
    implementation_not_blocked: bool
    rc004_live_denied: bool
    execution_authority_denied: bool = True

    def as_dict(self) -> dict[str, bool]:
        payload = asdict(self)
        payload["execution_authority_denied"] = True
        payload["authenticated_online"] = bool(self.authenticated_online)
        return payload

    def __post_init__(self) -> None:
        if not self.execution_authority_denied:
            raise ValueError("execution_authority_denied must remain True")


@dataclass(frozen=True)
class HardenedScores:
    implementation_maturity_score: int
    operational_readiness_score: int
    aggregate_qualification_score: int
    readiness_label: str
    mandatory_gate_results: MandatoryGateResults
    score_formula_version: str = SCORE_FORMULA_VERSION
    uncapped_operational_readiness_score: int = 0
    uncapped_aggregate_qualification_score: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "implementation_maturity_score": self.implementation_maturity_score,
            "operational_readiness_score": self.operational_readiness_score,
            "aggregate_qualification_score": self.aggregate_qualification_score,
            "readiness_label": self.readiness_label,
            "mandatory_gate_results": self.mandatory_gate_results.as_dict(),
            "score_formula_version": self.score_formula_version,
            "uncapped_operational_readiness_score": self.uncapped_operational_readiness_score,
            "uncapped_aggregate_qualification_score": self.uncapped_aggregate_qualification_score,
            "diagnostics": dict(self.diagnostics),
        }


def compute_implementation_maturity_score(
    *,
    implementation_status: str,
    audit_classification: str,
    capability_profile_ok: bool,
    provider_compatible: bool,
    certification_readiness: bool,
) -> int:
    status = str(implementation_status or "NOT_STARTED").upper()
    classification = str(audit_classification or "NOT_STARTED").upper()
    if status == "BLOCKED" or classification == "BLOCKED":
        return 0

    score = 0
    if capability_profile_ok:
        score += 25
    if provider_compatible:
        score += 35
    if certification_readiness:
        score += 20
    if status == "PARTIAL":
        score += 10
    elif status == "COMPLETE":
        score += 20
    elif status == "NOT_STARTED":
        score += 0
    return _clamp(score)


def compute_operational_readiness_raw(
    *,
    registry_entry_ok: bool,
    schema_compatible: bool,
    governance_aligned: bool,
    rc004_live_denied: bool,
    authorization_ttl_classified: bool,
    credentials_configured: bool,
    endpoint_configured: bool,
) -> int:
    score = 0
    if registry_entry_ok:
        score += 25
    if schema_compatible:
        score += 15
    if governance_aligned:
        score += 15
    if rc004_live_denied:
        score += 15
    if authorization_ttl_classified:
        score += 10
    if credentials_configured:
        score += 10
    if endpoint_configured:
        score += 10
    return _clamp(score)


def apply_operational_caps(
    raw_ops: int,
    *,
    registry_valid: bool,
    configured_readiness: str,
    credentials_present: bool,
) -> int:
    """Mandatory operational caps.

    - invalid/missing/suspended registry → 0
    - NOT_CONFIGURED or credentials absent → <= 25
    """
    if not registry_valid:
        return 0
    score = _clamp(raw_ops)
    if str(configured_readiness).upper() == "NOT_CONFIGURED" or not credentials_present:
        score = min(score, 25)
    return score


def compute_aggregate_qualification_score(
    implementation_maturity_score: int,
    operational_readiness_score: int,
    *,
    implementation_blocked: bool,
) -> tuple[int, int]:
    """Return (capped_aggregate, uncapped_aggregate).

    Aggregate = floor((impl + ops) / 2).
    Implementation BLOCKED → aggregate <= 25.
    """
    uncapped = _clamp((int(implementation_maturity_score) + int(operational_readiness_score)) // 2)
    capped = uncapped
    if implementation_blocked:
        capped = min(capped, 25)
    return capped, uncapped


def compute_hardened_scores(
    *,
    implementation_status: str,
    audit_classification: str,
    capability_profile_ok: bool,
    provider_compatible: bool,
    certification_readiness: bool,
    registry_entry_ok: bool,
    schema_compatible: bool,
    governance_aligned: bool,
    rc004_live_denied: bool,
    authorization_ttl_classified: bool,
    credentials_configured: bool,
    endpoint_configured: bool,
    configured_readiness: str,
    authenticated_online: bool = False,
) -> HardenedScores:
    """Compute all three scores with mandatory caps and readiness label."""
    impl_blocked = (
        str(implementation_status).upper() == "BLOCKED"
        or str(audit_classification).upper() == "BLOCKED"
    )
    impl = compute_implementation_maturity_score(
        implementation_status=implementation_status,
        audit_classification=audit_classification,
        capability_profile_ok=capability_profile_ok,
        provider_compatible=provider_compatible,
        certification_readiness=certification_readiness,
    )
    raw_ops = compute_operational_readiness_raw(
        registry_entry_ok=registry_entry_ok,
        schema_compatible=schema_compatible,
        governance_aligned=governance_aligned,
        rc004_live_denied=rc004_live_denied,
        authorization_ttl_classified=authorization_ttl_classified,
        credentials_configured=credentials_configured,
        endpoint_configured=endpoint_configured,
    )
    ops = apply_operational_caps(
        raw_ops,
        registry_valid=registry_entry_ok,
        configured_readiness=configured_readiness,
        credentials_present=credentials_configured,
    )
    aggregate, uncapped_agg = compute_aggregate_qualification_score(
        impl, ops, implementation_blocked=impl_blocked
    )
    label = readiness_label_for_score(aggregate)
    gates = MandatoryGateResults(
        registry_valid=bool(registry_entry_ok),
        configuration_present=bool(endpoint_configured),
        credentials_present=bool(credentials_configured),
        authenticated_online=bool(authenticated_online),
        implementation_not_blocked=not impl_blocked,
        rc004_live_denied=bool(rc004_live_denied),
        execution_authority_denied=True,
    )
    return HardenedScores(
        implementation_maturity_score=impl,
        operational_readiness_score=ops,
        aggregate_qualification_score=aggregate,
        readiness_label=label,
        mandatory_gate_results=gates,
        score_formula_version=SCORE_FORMULA_VERSION,
        uncapped_operational_readiness_score=raw_ops,
        uncapped_aggregate_qualification_score=uncapped_agg,
        diagnostics={
            "implementation_blocked": impl_blocked,
            "score_alone_cannot_advance_state": True,
        },
    )


def build_state_evidence_flags(
    *,
    registry_entry_ok: bool,
    capability_profile_ok: bool,
    schema_compatible: bool,
    rc004_live_denied: bool,
    authorization_ttl_classified: bool,
    provider_compatible: bool,
    hard_blocked: bool,
    endpoint_configured: bool,
    credentials_configured: bool,
    authenticated_online: bool,
    certification_readiness: bool,
) -> dict[str, bool]:
    """Boolean gates for the state machine. Scores are intentionally excluded."""
    configuration_present = bool(endpoint_configured)
    # Missing configuration cannot reach PRECHECK_READY or above.
    precheck_ready = (
        configuration_present
        and capability_profile_ok
        and schema_compatible
        and rc004_live_denied
        and authorization_ttl_classified
        and registry_entry_ok
        and provider_compatible
        and not hard_blocked
    )
    config_ready = configuration_present and schema_compatible and precheck_ready
    # Missing credentials cannot reach AUTH_READY.
    auth_config_ready = bool(credentials_configured) and config_ready
    # No authenticated online result cannot reach READ_ONLY_READY.
    read_only_framework_ready = bool(authenticated_online) and auth_config_ready and (
        certification_readiness or provider_compatible
    )
    qualification_complete = (
        bool(authenticated_online)
        and auth_config_ready
        and read_only_framework_ready
        and registry_entry_ok
        and provider_compatible
        and not hard_blocked
    )
    return {
        "precheck_ready": precheck_ready,
        "config_ready": config_ready,
        "auth_config_ready": auth_config_ready,
        "read_only_framework_ready": read_only_framework_ready,
        "qualification_complete": qualification_complete,
    }
