"""Phase 193 — deterministic multi-broker readiness matrix (offline)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from backend.app.brokers.multi_broker_readiness.audit_matrix import BROKER_AUDIT_MATRIX
from backend.app.brokers.operational_qualification.workflow import qualify_broker
from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository
from backend.app.governance.enterprise_certification_registry.seed import seed_phase_registry

DEFAULT_BROKERS: tuple[str, ...] = (
    "OANDA",
    "COINBASE",
    "IBKR",
    "BINANCE",
    "QUESTRADE",
    "PLUGIN",
)


@dataclass(frozen=True)
class BrokerReadinessRow:
    broker: str
    implementation_capability: str
    configured_readiness: str
    read_only_qualification: str
    live_execution_certification: str
    qualification_stage: str
    implementation_maturity_score: int
    operational_readiness_score: int
    aggregate_qualification_score: int
    readiness_label: str
    readiness_score: int  # alias of aggregate
    audit_classification: str
    blockers: tuple[str, ...]
    execution_authority: bool = False
    evidence_hash: str = ""
    score_formula_version: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_authority"] = False
        payload["live_execution_certification"] = "NOT_AUTHORIZED"
        payload["blockers"] = list(self.blockers)
        return payload


def build_broker_readiness_matrix(
    env: Mapping[str, Any] | None = None,
    *,
    brokers: Sequence[str] | None = None,
    repository: RegistryRepository | None = None,
    timestamp: str = "2026-08-01T12:00:00Z",
) -> tuple[BrokerReadinessRow, ...]:
    """Produce deterministic readiness rows. Empty env yields config-gated stages."""
    repo = repository if repository is not None else seed_phase_registry()
    rows: list[BrokerReadinessRow] = []
    for broker in brokers or DEFAULT_BROKERS:
        key = str(broker).upper()
        result = qualify_broker(
            key,
            env,
            repository=repo,
            timestamp=timestamp,
            qualification_id=f"oq-matrix-{key.lower()}",
        )
        audit = BROKER_AUDIT_MATRIX.get(key, {})
        rows.append(
            BrokerReadinessRow(
                broker=key,
                implementation_capability=result.evidence.implementation_capability
                or str(audit.get("implementation_status", "NOT_STARTED")),
                configured_readiness=result.evidence.configured_readiness,
                read_only_qualification=result.evidence.read_only_qualification,
                live_execution_certification="NOT_AUTHORIZED",
                qualification_stage=result.stage,
                implementation_maturity_score=result.implementation_maturity_score,
                operational_readiness_score=result.operational_readiness_score,
                aggregate_qualification_score=result.aggregate_qualification_score,
                readiness_label=result.readiness_label,
                readiness_score=result.aggregate_qualification_score,
                audit_classification=str(audit.get("classification", "NOT_STARTED")),
                blockers=result.evidence.blocker_list,
                execution_authority=False,
                evidence_hash=result.evidence.evidence_hash,
                score_formula_version=result.evidence.score_formula_version,
            )
        )
    return tuple(sorted(rows, key=lambda r: r.broker))
