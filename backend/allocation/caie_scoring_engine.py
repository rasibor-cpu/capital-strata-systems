from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .opportunity_proposal import OpportunityProposal
from .opportunity_validator import validate_opportunity_proposal


@dataclass(frozen=True)
class CAIEScore:
    proposal_id: str
    expected_value_pct: Decimal
    capital_efficiency: Decimal
    confidence_bonus: Decimal
    risk_penalty: Decimal
    liquidity_penalty: Decimal
    regime_penalty: Decimal
    total_score: Decimal
    status: str


class CAIEScoringEngine:
    """Shadow-only risk-adjusted scoring for validated CAIE proposals."""

    @staticmethod
    def score(proposal: OpportunityProposal) -> CAIEScore:
        validation = validate_opportunity_proposal(proposal)
        if not validation.valid or validation.proposal is None:
            raise ValueError("invalid opportunity proposal")

        item = validation.proposal
        one = Decimal("1")
        expected_value = (
            item.probability_win * item.expected_return_pct
            - (one - item.probability_win) * item.max_drawdown_pct
        )

        # Confidence is deliberately beneficial only when expected value is
        # already positive; confidence cannot rescue a negative-EV proposal.
        confidence_bonus = (
            expected_value * item.confidence * Decimal("0.25")
            if expected_value > 0
            else Decimal("0")
        )

        risk_penalty = item.max_drawdown_pct * Decimal("0.35")
        liquidity_penalty = (one - item.liquidity_score) * Decimal("0.15")
        regime_penalty = (one - item.regime_alignment) * Decimal("0.15")

        # A bounded return-to-risk efficiency term rewards more efficient
        # opportunities without allowing capital amount alone to dominate.
        denominator = item.max_drawdown_pct + Decimal("0.01")
        capital_efficiency = expected_value / denominator

        efficiency_bonus = (
            min(capital_efficiency, Decimal("1")) * Decimal("0.05")
            if capital_efficiency > 0
            else Decimal("0")
        )

        total = (
            expected_value
            + confidence_bonus
            + efficiency_bonus
            - risk_penalty
            - liquidity_penalty
            - regime_penalty
        )

        q = Decimal("0.000001")
        return CAIEScore(
            proposal_id=item.proposal_id,
            expected_value_pct=expected_value.quantize(q),
            capital_efficiency=capital_efficiency.quantize(q),
            confidence_bonus=confidence_bonus.quantize(q),
            risk_penalty=risk_penalty.quantize(q),
            liquidity_penalty=liquidity_penalty.quantize(q),
            regime_penalty=regime_penalty.quantize(q),
            total_score=total.quantize(q),
            status="SHADOW_ONLY",
        )
