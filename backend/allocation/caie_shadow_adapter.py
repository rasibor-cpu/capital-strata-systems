from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from .caie_portfolio_optimizer import CAIEPortfolioOptimizer
from .caie_scoring_engine import CAIEScoringEngine


class CAIEShadowAdapter:
    """Run the CAIE advisory pipeline (score + optimize) in fail-closed shadow mode."""

    def __init__(
        self,
        *,
        scoring_engine: CAIEScoringEngine | None = None,
        portfolio_optimizer: CAIEPortfolioOptimizer | None = None,
    ) -> None:
        self.scoring_engine = scoring_engine or CAIEScoringEngine()
        self.portfolio_optimizer = portfolio_optimizer or CAIEPortfolioOptimizer()

    def generate_advisory(
        self,
        validated_proposals: Sequence[Mapping[str, Any]] | None,
        *,
        available_capital: float,
        proposal_contexts: Mapping[str, Mapping[str, Any]] | None = None,
        default_broker: str = "UNKNOWN",
        asset_class_caps: Mapping[str, float] | None = None,
        broker_caps: Mapping[str, float] | None = None,
        min_quality_score: float = 50.0,
        concentration_penalty_weight: float = 20.0,
        diversification_bonus: float = 2.0,
        runtime_timestamp: str | None = None,
    ) -> dict[str, Any]:
        ts = runtime_timestamp or datetime.now(timezone.utc).isoformat()

        try:
            capital = float(available_capital)
        except (TypeError, ValueError):
            return self._unavailable("available_capital_invalid", ts)

        if capital < 0.0:
            return self._unavailable("available_capital_negative", ts)

        if not isinstance(validated_proposals, Sequence):
            return self._unavailable("validated_proposals_must_be_sequence", ts)

        if not validated_proposals:
            return self._safe_empty("NO_OPPORTUNITIES", capital, ts)

        contexts = proposal_contexts if isinstance(proposal_contexts, Mapping) else {}
        opportunities: list[dict[str, Any]] = []

        for proposal in validated_proposals:
            if not isinstance(proposal, Mapping):
                return self._unavailable("invalid_proposal_payload", ts)
            if bool(proposal.get("valid")) is not True:
                return self._unavailable("proposal_not_validated", ts)

            normalized = proposal.get("normalized")
            if not isinstance(normalized, Mapping):
                return self._unavailable("validated_payload_missing_normalized", ts)

            proposal_id = str(normalized.get("proposal_id") or "").strip()
            if not proposal_id:
                return self._unavailable("validated_payload_missing_proposal_id", ts)

            context = contexts.get(proposal_id, {})
            if not isinstance(context, Mapping):
                return self._unavailable("proposal_context_invalid", ts)

            score_result = self.scoring_engine.score(proposal, context=context)
            if bool(score_result.get("valid")) is not True:
                return self._unavailable("scoring_unavailable", ts)

            broker = str(context.get("broker") or default_broker).strip().upper() or "UNKNOWN"
            opportunities.append(
                {
                    "proposal": proposal,
                    "score": score_result,
                    "broker": broker,
                }
            )

        optimized = self.portfolio_optimizer.optimize(
            opportunities,
            capital,
            asset_class_caps=asset_class_caps,
            broker_caps=broker_caps,
            min_quality_score=min_quality_score,
            concentration_penalty_weight=concentration_penalty_weight,
            diversification_bonus=diversification_bonus,
        )

        if bool(optimized.get("valid")) is not True:
            return self._unavailable("optimizer_unavailable", ts)

        return {
            "caie_status": "AVAILABLE",
            "advisory_only": True,
            "shadow_mode": True,
            "ranked_opportunities": optimized.get("ranked_opportunities", []),
            "selected_opportunities": optimized.get("selected_opportunities", []),
            "recommended_allocations": optimized.get("recommended_capital_allocations", []),
            "portfolio_score": optimized.get("portfolio_score"),
            "unused_capital": optimized.get("unused_capital"),
            "execution_action": "NO_EXECUTION",
            "runtime_timestamp": ts,
            "reason": "caie_advisory_generated",
        }

    @staticmethod
    def _safe_empty(status: str, available_capital: float, timestamp: str) -> dict[str, Any]:
        return {
            "caie_status": status,
            "advisory_only": True,
            "shadow_mode": True,
            "ranked_opportunities": [],
            "selected_opportunities": [],
            "recommended_allocations": [],
            "portfolio_score": 0.0,
            "unused_capital": round(float(available_capital), 6),
            "execution_action": "NO_EXECUTION",
            "runtime_timestamp": timestamp,
            "reason": "no_valid_opportunities",
        }

    @staticmethod
    def _unavailable(reason: str, timestamp: str) -> dict[str, Any]:
        return {
            "caie_status": "UNAVAILABLE",
            "advisory_only": True,
            "shadow_mode": True,
            "ranked_opportunities": [],
            "selected_opportunities": [],
            "recommended_allocations": [],
            "portfolio_score": None,
            "unused_capital": None,
            "execution_action": "NO_EXECUTION",
            "runtime_timestamp": timestamp,
            "reason": reason,
        }


def generate_caie_shadow_advisory(
    validated_proposals: Sequence[Mapping[str, Any]] | None,
    *,
    available_capital: float,
    proposal_contexts: Mapping[str, Mapping[str, Any]] | None = None,
    default_broker: str = "UNKNOWN",
    asset_class_caps: Mapping[str, float] | None = None,
    broker_caps: Mapping[str, float] | None = None,
    min_quality_score: float = 50.0,
    concentration_penalty_weight: float = 20.0,
    diversification_bonus: float = 2.0,
    runtime_timestamp: str | None = None,
) -> dict[str, Any]:
    return CAIEShadowAdapter().generate_advisory(
        validated_proposals,
        available_capital=available_capital,
        proposal_contexts=proposal_contexts,
        default_broker=default_broker,
        asset_class_caps=asset_class_caps,
        broker_caps=broker_caps,
        min_quality_score=min_quality_score,
        concentration_penalty_weight=concentration_penalty_weight,
        diversification_bonus=diversification_bonus,
        runtime_timestamp=runtime_timestamp,
    )
