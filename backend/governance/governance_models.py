"""Canonical read-only Enterprise Governance contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceDomain(str, Enum):
    SECURITY = "SECURITY"
    IDENTITY = "IDENTITY"
    OAUTH = "OAUTH"
    SECRETS = "SECRETS"
    BROKER_RUNTIME = "BROKER_RUNTIME"
    OPTIONS_INCOME = "OPTIONS_INCOME"
    TRADING_RUNTIME = "TRADING_RUNTIME"
    REPORTING = "REPORTING"
    AUDIT = "AUDIT"
    COMPLIANCE = "COMPLIANCE"
    OPERATIONS = "OPERATIONS"
    RISK = "RISK"
    BUSINESS_CONTINUITY = "BUSINESS_CONTINUITY"


class EvidenceStatus(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class GovernanceEvidence:
    evidence_id: str
    domain: GovernanceDomain
    control: str
    status: EvidenceStatus
    source: str
    reference: str
    observed_at: str
    owner: str
    verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["domain"] = self.domain.value
        payload["status"] = self.status.value
        payload["contains_secret_material"] = False
        payload["execution_allowed"] = False
        return payload


@dataclass(frozen=True)
class ReadinessResult:
    framework: str
    percentage: float
    controls_total: int
    controls_satisfied: int
    controls_missing: int
    controls_failed: int
    evidence: tuple[dict[str, Any], ...]
    blockers: tuple[str, ...]
    formal_certification_claimed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "execution_allowed": False}


class RiskCategory(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    TECHNICAL = "TECHNICAL"
    SECURITY = "SECURITY"
    PROVIDER = "PROVIDER"
    BROKER = "BROKER"
    MARKET_DATA = "MARKET_DATA"
    REGULATORY = "REGULATORY"


class RiskRating(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class EnterpriseRisk:
    risk_id: str
    category: RiskCategory
    title: str
    severity: RiskRating
    likelihood: RiskRating
    owner: str
    mitigation: str
    review_date: str
    certification_status: str
    evidence_references: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["category"] = self.category.value
        payload["severity"] = self.severity.value
        payload["likelihood"] = self.likelihood.value
        payload["execution_allowed"] = False
        return payload


__all__ = [
    "EnterpriseRisk",
    "EvidenceStatus",
    "GovernanceDomain",
    "GovernanceEvidence",
    "ReadinessResult",
    "RiskCategory",
    "RiskRating",
    "utc_now",
]
