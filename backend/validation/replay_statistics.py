from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .replay_models import ReplayDecision, ReplayModelsError


class ReplayStatisticsError(RuntimeError):
    """Fail-closed exception for replay statistics generation."""


@dataclass(frozen=True)
class ReplayStatistics:
    number_of_candidates: int
    number_of_approved_trades: int
    blocked_trades: int
    average_confidence: float
    average_allocation: float
    strategy_distribution: dict[str, int]
    regime_distribution: dict[str, int]
    decision_distribution: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def empty() -> "ReplayStatistics":
        return ReplayStatistics(
            number_of_candidates=0,
            number_of_approved_trades=0,
            blocked_trades=0,
            average_confidence=0.0,
            average_allocation=0.0,
            strategy_distribution={},
            regime_distribution={},
            decision_distribution={},
        )


def build_replay_statistics(decisions: Iterable[ReplayDecision | Mapping[str, Any]]) -> ReplayStatistics:
    if decisions is None:
        raise ReplayStatisticsError("decisions must not be None")

    normalized: list[ReplayDecision] = []
    for decision in decisions:
        normalized.append(_normalize_decision(decision))

    if not normalized:
        return ReplayStatistics.empty()

    strategy_counts = Counter(decision.selected_strategy for decision in normalized)
    regime_counts = Counter(decision.market_regime for decision in normalized)
    decision_counts = Counter(decision.decision for decision in normalized)
    confidence_total = sum(float(decision.confidence) for decision in normalized)
    allocation_total = sum(_allocation_amount(decision.allocation) for decision in normalized)

    approved = sum(1 for decision in normalized if decision.decision == "ALLOW")
    blocked = sum(1 for decision in normalized if decision.decision == "BLOCK")

    return ReplayStatistics(
        number_of_candidates=len(normalized),
        number_of_approved_trades=approved,
        blocked_trades=blocked,
        average_confidence=round(confidence_total / len(normalized), 8),
        average_allocation=round(allocation_total / len(normalized), 8),
        strategy_distribution={key: strategy_counts[key] for key in sorted(strategy_counts.keys())},
        regime_distribution={key: regime_counts[key] for key in sorted(regime_counts.keys())},
        decision_distribution={key: decision_counts[key] for key in sorted(decision_counts.keys())},
    )


def _allocation_amount(allocation: Mapping[str, Any]) -> float:
    if not isinstance(allocation, Mapping):
        raise ReplayStatisticsError("allocation must be a mapping")
    for field in ("allocation_amount", "recommended_capital", "capital"):
        if field in allocation and allocation.get(field) is not None:
            try:
                return float(allocation[field])
            except (TypeError, ValueError) as exc:
                raise ReplayStatisticsError(f"allocation field {field} must be numeric") from exc
    return 0.0


def _normalize_decision(decision: ReplayDecision | Mapping[str, Any]) -> ReplayDecision:
    if isinstance(decision, ReplayDecision):
        return decision
    if not isinstance(decision, Mapping):
        raise ReplayStatisticsError("decision must be a mapping or ReplayDecision")

    required = {
        "timestamp",
        "symbol",
        "market_regime",
        "selected_strategy",
        "allocation",
        "position_size",
        "risk_score",
        "confidence",
        "decision",
        "exit_plan",
    }
    missing = [field for field in required if field not in decision]
    if missing:
        raise ReplayStatisticsError(f"decision missing required fields: {', '.join(missing)}")

    diagnostics = decision.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        raise ReplayStatisticsError("decision diagnostics must be a mapping")

    try:
        return ReplayDecision(
            timestamp=str(decision["timestamp"]).strip(),
            symbol=str(decision["symbol"]).strip().upper(),
            market_regime=str(decision["market_regime"]).strip().upper(),
            selected_strategy=str(decision["selected_strategy"]).strip(),
            allocation=dict(decision["allocation"]),
            position_size=dict(decision["position_size"]),
            risk_score=float(decision["risk_score"]),
            confidence=float(decision["confidence"]),
            decision=str(decision["decision"]).strip().upper(),
            exit_plan=dict(decision["exit_plan"]),
            diagnostics=dict(diagnostics),
        )
    except (TypeError, ValueError) as exc:
        raise ReplayStatisticsError(str(exc)) from exc
