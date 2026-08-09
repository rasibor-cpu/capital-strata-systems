"""Phase 193 — controlled multi-broker read-only operational qualification.

NO NETWORK. NO AUTHENTICATION. NO EXECUTION. NO RUNTIME ACTIVATION.
"""

from __future__ import annotations

from backend.app.brokers.operational_qualification.evidence import (
    QualificationEvidence,
    build_qualification_evidence,
    hash_qualification_payload,
)
from backend.app.brokers.operational_qualification.firewall import (
    verify_operational_qualification_firewall,
)
from backend.app.brokers.operational_qualification.matrix import (
    BrokerReadinessRow,
    build_broker_readiness_matrix,
)
from backend.app.brokers.operational_qualification.precheck import (
    OperationalQualificationPrecheck,
    run_operational_qualification_precheck,
)
from backend.app.brokers.operational_qualification.scoring import (
    SCORE_FORMULA_VERSION,
    HardenedScores,
    MandatoryGateResults,
    build_state_evidence_flags,
    compute_hardened_scores,
    readiness_label_for_score,
)
from backend.app.brokers.operational_qualification.states import (
    QUALIFICATION_STATES,
    QualificationStateMachine,
    TransitionResult,
)
from backend.app.brokers.operational_qualification.workflow import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    OperationalQualificationResult,
    qualify_broker,
)

__all__ = [
    "FRAMEWORK_VERSION",
    "SCHEMA_VERSION",
    "SCORE_FORMULA_VERSION",
    "QUALIFICATION_STATES",
    "QualificationStateMachine",
    "TransitionResult",
    "OperationalQualificationPrecheck",
    "run_operational_qualification_precheck",
    "QualificationEvidence",
    "build_qualification_evidence",
    "hash_qualification_payload",
    "HardenedScores",
    "MandatoryGateResults",
    "compute_hardened_scores",
    "build_state_evidence_flags",
    "readiness_label_for_score",
    "OperationalQualificationResult",
    "qualify_broker",
    "BrokerReadinessRow",
    "build_broker_readiness_matrix",
    "verify_operational_qualification_firewall",
]

# Phase 194 canonical broker-path reconciliation.
from backend.app.brokers.operational_qualification.canonical_path import (
    CANONICAL_TIER1,
    CanonicalBrokerQualificationPath,
    build_canonical_broker_path_matrix,
    canonical_broker_path,
    phase194_safety_contract,
)
