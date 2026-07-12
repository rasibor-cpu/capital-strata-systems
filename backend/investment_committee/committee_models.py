from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


APPROVED = "APPROVED"
APPROVED_LOW_PRIORITY = "APPROVED_LOW_PRIORITY"
WAIT = "WAIT"
REJECT = "REJECT"
INSUFFICIENT_EDGE = "INSUFFICIENT_EDGE"
CAPITAL_BETTER_DEPLOYED = "CAPITAL_BETTER_DEPLOYED"
RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
PORTFOLIO_CONFLICT = "PORTFOLIO_CONFLICT"
RISK_VETO = "RISK_VETO"
PORTFOLIO_VETO = "PORTFOLIO_VETO"
LIQUIDITY_VETO = "LIQUIDITY_VETO"
OPERATIONAL_VETO = "OPERATIONAL_VETO"

APPROVE = "APPROVE"
APPROVE_WITH_CAUTION = "APPROVE_WITH_CAUTION"
ABSTAIN = "ABSTAIN"

DECISIONS = (
    APPROVED,
    APPROVED_LOW_PRIORITY,
    WAIT,
    REJECT,
    INSUFFICIENT_EDGE,
    CAPITAL_BETTER_DEPLOYED,
    RISK_LIMIT_EXCEEDED,
    PORTFOLIO_CONFLICT,
    RISK_VETO,
    PORTFOLIO_VETO,
    LIQUIDITY_VETO,
    OPERATIONAL_VETO,
)

VOTES = (APPROVE, APPROVE_WITH_CAUTION, WAIT, REJECT, ABSTAIN)


@dataclass(frozen=True)
class CommitteeOpportunity:
    opportunity_id: str
    symbol: str
    asset_class: str
    sector: str
    strategy: str
    broker: str
    requested_capital: float
    expected_return: float
    probability_of_success: float
    expected_drawdown: float
    expected_holding_period: float
    capital_efficiency: float
    portfolio_correlation: float
    sector_concentration: float
    asset_allocation_impact: float
    regime_suitability: float
    liquidity: float
    spread_quality: float
    execution_cost: float
    volatility: float
    risk_budget_consumption: float
    strategy_confidence: float
    signal_quality: float
    historical_similarity: float
    decision_confidence: float
    operational_readiness: float
    market_health: float
    raw: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(frozen=True)
class CommitteeScorecard:
    committee_score: float
    dimensions: dict[str, float]
    blockers: list[str]
    strengths: list[str]
    weaknesses: list[str]
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(frozen=True)
class CommitteeVote:
    committee: str
    vote: str
    confidence: float
    committee_score: float
    reason: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    veto: str = ""
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(frozen=True)
class CommitteeEvaluation:
    opportunity: CommitteeOpportunity
    scorecard: CommitteeScorecard
    decision: str
    capital_rank: int
    opportunity_rank: int
    recommended_capital: float
    capital_displacement: str
    replacement_candidate: str
    recommendation: str
    explanation: str
    committee_votes: list[CommitteeVote] = field(default_factory=list)
    consensus: dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = _json_safe(asdict(self))
        payload["opportunity"] = self.opportunity.as_dict()
        payload["scorecard"] = self.scorecard.as_dict()
        payload["committee_votes"] = [vote.as_dict() for vote in self.committee_votes]
        return payload


@dataclass(frozen=True)
class CommitteeReport:
    generated_at: str
    committee_score: float
    decision: str
    evaluations: list[CommitteeEvaluation]
    capital_plan: list[dict[str, Any]]
    recommendations: list[str]
    blockers: list[str]
    consensus_summary: dict[str, Any] = field(default_factory=dict)
    committee_history: list[dict[str, Any]] = field(default_factory=list)
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    payload_version: str = "css.phase167.multi_committee_institutional_decision.v1"

    @classmethod
    def empty(cls, *, reason: str = "No candidate opportunities supplied.") -> "CommitteeReport":
        return cls(
            generated_at=datetime.now(timezone.utc).isoformat(),
            committee_score=0.0,
            decision=WAIT,
            evaluations=[],
            capital_plan=[],
            recommendations=[reason],
            blockers=[],
        )

    def as_dict(self) -> dict[str, Any]:
        payload = _json_safe(asdict(self))
        payload["evaluations"] = [item.as_dict() for item in self.evaluations]
        return payload


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
