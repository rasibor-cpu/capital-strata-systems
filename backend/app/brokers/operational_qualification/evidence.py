"""Phase 193 — immutable qualification evidence (offline)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from backend.app.brokers.operational_qualification.scoring import SCORE_FORMULA_VERSION

FRAMEWORK_VERSION = "193.2"
SCHEMA_VERSION = "193.2"

FORBIDDEN_EVIDENCE_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "client_secret",
    "Authorization: Bearer",
    "refresh_token=",
    "api_secret",
    "password=",
)


def hash_qualification_payload(payload: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 over canonical JSON (sorted keys, compact separators)."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class QualificationEvidence:
    qualification_id: str
    broker: str
    asset_class: str
    provider_name: str
    provider_version: str
    schema_version: str
    capability_profile: Mapping[str, Any]
    registry_generation: int
    rc004_posture: str
    qualification_stage: str
    readiness_score: int  # alias of aggregate_qualification_score
    implementation_maturity_score: int
    operational_readiness_score: int
    aggregate_qualification_score: int
    readiness_label: str
    mandatory_gate_results: Mapping[str, bool]
    score_formula_version: str
    blocker_count: int
    blocker_list: tuple[str, ...]
    evidence_hash: str
    generated_timestamp: str
    execution_authority: bool = False
    implementation_capability: str = ""
    configured_readiness: str = ""
    read_only_qualification: str = ""
    live_execution_certification: str = "NOT_AUTHORIZED"
    authorization_ttl_status: str = "N/A"
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_authority"] = False
        payload["live_execution_certification"] = "NOT_AUTHORIZED"
        payload["blocker_list"] = list(self.blocker_list)
        payload["mandatory_gate_results"] = dict(self.mandatory_gate_results)
        return payload

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("qualification evidence must not grant execution_authority")
        if self.live_execution_certification not in {"NOT_AUTHORIZED", "BLOCKED", "NOT_STARTED"}:
            raise ValueError("live_execution_certification must remain non-authorized")
        if self.diagnostics.get("secret_values_captured"):
            raise ValueError("secret material must not appear in evidence")
        if self.read_only_qualification == "NOT_READY" and self.qualification_stage in {
            "READ_ONLY_READY",
            "QUALIFIED",
        }:
            raise ValueError("NOT_READY cannot be QUALIFIED or READ_ONLY_READY")
        if self.blocker_count != len(self.blocker_list):
            raise ValueError("blocker_count must equal len(blocker_list)")
        if self.readiness_score != self.aggregate_qualification_score:
            raise ValueError("readiness_score must equal aggregate_qualification_score")
        blob = json.dumps(self.as_dict(), sort_keys=True, default=str).lower()
        for marker in ("begin private key", "authorization: bearer", "refresh_token="):
            if marker in blob:
                raise ValueError(f"forbidden_secret_marker:{marker}")


def build_qualification_evidence(
    *,
    qualification_id: str,
    broker: str,
    asset_class: str,
    provider_name: str,
    provider_version: str,
    schema_version: str,
    capability_profile: Mapping[str, Any],
    registry_generation: int,
    rc004_posture: str,
    qualification_stage: str,
    implementation_maturity_score: int,
    operational_readiness_score: int,
    aggregate_qualification_score: int,
    readiness_label: str,
    mandatory_gate_results: Mapping[str, bool],
    blocker_list: Sequence[str],
    generated_timestamp: str,
    score_formula_version: str = SCORE_FORMULA_VERSION,
    implementation_capability: str = "",
    configured_readiness: str = "",
    read_only_qualification: str = "",
    authorization_ttl_status: str = "N/A",
    diagnostics: Mapping[str, Any] | None = None,
) -> QualificationEvidence:
    diag = dict(diagnostics or {})
    diag.setdefault("redacted", True)
    diag.setdefault("secret_values_captured", False)
    diag.setdefault("authentication_performed", False)
    diag.setdefault("network_contact_performed", False)
    diag.setdefault("read_only_ttl_is_not_live_authority", True)
    diag.setdefault("score_alone_cannot_advance_state", True)

    blockers = tuple(sorted(str(b) for b in blocker_list))
    gates = dict(mandatory_gate_results)
    gates["execution_authority_denied"] = True

    # Enforce NOT_READY cannot claim RO/QUALIFIED stages in evidence construction.
    stage = qualification_stage
    ro_qual = read_only_qualification
    if ro_qual == "NOT_READY" and stage in {"READ_ONLY_READY", "QUALIFIED"}:
        stage = "AUTH_READY" if gates.get("credentials_present") else (
            "CONFIG_READY" if gates.get("configuration_present") else "NOT_STARTED"
        )
        ro_qual = "NOT_READY"

    material = {
        "qualification_id": qualification_id,
        "broker": str(broker).upper(),
        "asset_class": str(asset_class).upper(),
        "provider_name": provider_name,
        "provider_version": provider_version,
        "schema_version": schema_version,
        "capability_profile": dict(capability_profile),
        "registry_generation": int(registry_generation),
        "rc004_posture": rc004_posture,
        "qualification_stage": stage,
        "implementation_maturity_score": int(implementation_maturity_score),
        "operational_readiness_score": int(operational_readiness_score),
        "aggregate_qualification_score": int(aggregate_qualification_score),
        "readiness_score": int(aggregate_qualification_score),
        "readiness_label": readiness_label,
        "mandatory_gate_results": gates,
        "score_formula_version": score_formula_version,
        "blocker_count": len(blockers),
        "blocker_list": list(blockers),
        "generated_timestamp": generated_timestamp,
        "execution_authority": False,
        "implementation_capability": implementation_capability,
        "configured_readiness": configured_readiness,
        "read_only_qualification": ro_qual,
        "live_execution_certification": "NOT_AUTHORIZED",
        "authorization_ttl_status": authorization_ttl_status,
        "framework_version": FRAMEWORK_VERSION,
    }
    digest = hash_qualification_payload(material)
    return QualificationEvidence(
        qualification_id=qualification_id,
        broker=str(broker).upper(),
        asset_class=str(asset_class).upper(),
        provider_name=provider_name,
        provider_version=provider_version,
        schema_version=schema_version,
        capability_profile=dict(capability_profile),
        registry_generation=int(registry_generation),
        rc004_posture=rc004_posture,
        qualification_stage=stage,
        readiness_score=int(aggregate_qualification_score),
        implementation_maturity_score=int(implementation_maturity_score),
        operational_readiness_score=int(operational_readiness_score),
        aggregate_qualification_score=int(aggregate_qualification_score),
        readiness_label=readiness_label,
        mandatory_gate_results=gates,
        score_formula_version=score_formula_version,
        blocker_count=len(blockers),
        blocker_list=blockers,
        evidence_hash=digest,
        generated_timestamp=generated_timestamp,
        execution_authority=False,
        implementation_capability=implementation_capability,
        configured_readiness=configured_readiness,
        read_only_qualification=ro_qual,
        live_execution_certification="NOT_AUTHORIZED",
        authorization_ttl_status=authorization_ttl_status,
        diagnostics=diag,
    )
