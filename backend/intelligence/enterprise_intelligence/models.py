"""DIP-005 Enterprise Intelligence data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION
from backend.intelligence.trade_dna.hashing import compute_content_hash


ENTERPRISE_INTELLIGENCE_VERSION = "css.enterprise_intelligence.v1"
ENTERPRISE_REPORT_VERSION = "css.enterprise_intelligence.report.v1"
ENTERPRISE_REPORT_SCHEMA_VERSION = "css.enterprise_intelligence.report.schema.v1"

ADVISORY_FLAGS = {
    "advisory_only": True,
    "execution_allowed": False,
    "capital_movement_allowed": False,
    "broker_action_allowed": False,
    "risk_limit_action_allowed": False,
    "trade_authorization_allowed": False,
    "runtime_control_allowed": False,
    "live_execution_allowed": False,
    "recommendations": False,
    "optimization": False,
}


def canonical_hash(payload: Mapping[str, Any]) -> str:
    return compute_content_hash(dict(payload))


@dataclass(frozen=True)
class EvidenceReference:
    trade_ids: tuple[str, ...] = ()
    dna_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    calculations: tuple[str, ...] = ()
    evidence_version: str = EVIDENCE_VERSION
    analysis_version: str = ANALYSIS_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trade_ids"] = list(self.trade_ids)
        payload["dna_ids"] = list(self.dna_ids)
        payload["edge_ids"] = list(self.edge_ids)
        payload["calculations"] = list(self.calculations)
        return payload


@dataclass(frozen=True)
class CapitalIntelligenceReport:
    generated_at: str
    period_days: int
    metrics: dict[str, Any]
    trends: tuple[dict[str, Any], ...]
    exposure_history: tuple[dict[str, Any], ...]
    evidence: EvidenceReference
    version: str = ENTERPRISE_INTELLIGENCE_VERSION
    advisory_flags: dict[str, bool] = field(default_factory=lambda: dict(ADVISORY_FLAGS))
    report_hash: str = ""

    def to_dict(
        self,
        *,
        include_hash: bool = True,
        include_caller_metadata: bool = True,
    ) -> dict[str, Any]:
        payload = asdict(self)
        payload["trends"] = list(self.trends)
        payload["exposure_history"] = list(self.exposure_history)
        payload["evidence"] = self.evidence.to_dict()
        if not include_hash:
            payload["report_hash"] = ""
        if not include_caller_metadata:
            payload["generated_at"] = None
        return payload

    def with_hash(self) -> "CapitalIntelligenceReport":
        payload = self.to_dict(include_hash=False, include_caller_metadata=False)
        return CapitalIntelligenceReport(
            generated_at=self.generated_at,
            period_days=self.period_days,
            metrics=self.metrics,
            trends=self.trends,
            exposure_history=self.exposure_history,
            evidence=self.evidence,
            version=self.version,
            advisory_flags=dict(self.advisory_flags),
            report_hash=canonical_hash(payload),
        )


@dataclass(frozen=True)
class ExecutiveIntelligenceSummary:
    generated_at: str
    summary: dict[str, Any]
    operational_alerts: tuple[dict[str, Any], ...]
    evidence: EvidenceReference
    version: str = ENTERPRISE_INTELLIGENCE_VERSION
    advisory_flags: dict[str, bool] = field(default_factory=lambda: dict(ADVISORY_FLAGS))
    summary_hash: str = ""

    def to_dict(
        self,
        *,
        include_hash: bool = True,
        include_caller_metadata: bool = True,
    ) -> dict[str, Any]:
        payload = asdict(self)
        payload["operational_alerts"] = list(self.operational_alerts)
        payload["evidence"] = self.evidence.to_dict()
        if not include_hash:
            payload["summary_hash"] = ""
        if not include_caller_metadata:
            payload["generated_at"] = None
        return payload

    def with_hash(self) -> "ExecutiveIntelligenceSummary":
        payload = self.to_dict(include_hash=False, include_caller_metadata=False)
        return ExecutiveIntelligenceSummary(
            generated_at=self.generated_at,
            summary=self.summary,
            operational_alerts=self.operational_alerts,
            evidence=self.evidence,
            version=self.version,
            advisory_flags=dict(self.advisory_flags),
            summary_hash=canonical_hash(payload),
        )


@dataclass(frozen=True)
class EnterpriseIntelligenceReport:
    generated_at: str | None
    sections: dict[str, Any]
    evidence: EvidenceReference
    report_schema_version: str = ENTERPRISE_REPORT_SCHEMA_VERSION
    analysis_version: str = ANALYSIS_VERSION
    evidence_version: str = EVIDENCE_VERSION
    generation_parameters: dict[str, Any] = field(default_factory=dict)
    canonical_report_id: str = ""
    report_type: str = "ENTERPRISE_INTELLIGENCE"
    version: str = ENTERPRISE_REPORT_VERSION
    advisory_flags: dict[str, bool] = field(default_factory=lambda: dict(ADVISORY_FLAGS))
    report_hash: str = ""

    def to_dict(
        self,
        *,
        include_hash: bool = True,
        include_caller_metadata: bool = True,
    ) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = self.evidence.to_dict()
        if not include_hash:
            payload["report_hash"] = ""
        if not include_caller_metadata:
            payload["generated_at"] = None
        return payload

    def with_hash(self) -> "EnterpriseIntelligenceReport":
        canonical_id = self.canonical_report_id or canonical_hash(
            {
                "report_type": self.report_type,
                "report_schema_version": self.report_schema_version,
                "analysis_version": self.analysis_version,
                "evidence_version": self.evidence_version,
                "generation_parameters": self.generation_parameters,
            }
        )
        canonical = EnterpriseIntelligenceReport(
            generated_at=self.generated_at,
            sections=self.sections,
            evidence=self.evidence,
            report_schema_version=self.report_schema_version,
            analysis_version=self.analysis_version,
            evidence_version=self.evidence_version,
            generation_parameters=self.generation_parameters,
            canonical_report_id=canonical_id,
            report_type=self.report_type,
            version=self.version,
            advisory_flags=dict(self.advisory_flags),
            report_hash="",
        )
        payload = canonical.to_dict(include_hash=False, include_caller_metadata=False)
        return EnterpriseIntelligenceReport(
            generated_at=self.generated_at,
            sections=self.sections,
            evidence=self.evidence,
            report_schema_version=self.report_schema_version,
            analysis_version=self.analysis_version,
            evidence_version=self.evidence_version,
            generation_parameters=self.generation_parameters,
            canonical_report_id=canonical_id,
            report_type=self.report_type,
            version=self.version,
            advisory_flags=dict(self.advisory_flags),
            report_hash=canonical_hash(payload),
        )
