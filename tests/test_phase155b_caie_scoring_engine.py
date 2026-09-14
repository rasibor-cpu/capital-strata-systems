from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.allocation import OpportunityProposal
from backend.allocation.caie_scoring_engine import CAIEScoringEngine


NOW = datetime(2026, 9, 14, 23, 45, tzinfo=timezone.utc)


def proposal(**overrides):
    values = {
        "proposal_id": "opp-1",
        "source": "shadow-test",
        "broker": "PAPER",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "side": "BUY",
        "probability_win": Decimal("0.70"),
        "confidence": Decimal("0.70"),
        "capital_required": Decimal("1000"),
        "max_drawdown_pct": Decimal("0.05"),
        "expected_return_pct": Decimal("0.08"),
        "liquidity_score": Decimal("0.90"),
        "regime_alignment": Decimal("0.90"),
        "observed_at_utc": NOW,
    }
    values.update(overrides)
    return OpportunityProposal(**values)


def test_positive_ev_scores_higher_than_negative_ev():
    positive = CAIEScoringEngine.score(proposal(proposal_id="positive"))
    negative = CAIEScoringEngine.score(
        proposal(
            proposal_id="negative",
            probability_win=Decimal("0.30"),
            expected_return_pct=Decimal("0.02"),
            max_drawdown_pct=Decimal("0.12"),
        )
    )
    assert positive.expected_value_pct > 0
    assert negative.expected_value_pct < 0
    assert positive.total_score > negative.total_score


def test_confidence_improves_score_only_when_ev_positive():
    low = CAIEScoringEngine.score(proposal(proposal_id="low", confidence=Decimal("0.20")))
    high = CAIEScoringEngine.score(proposal(proposal_id="high", confidence=Decimal("0.90")))
    assert high.total_score > low.total_score

    neg_low = CAIEScoringEngine.score(
        proposal(
            proposal_id="neg-low",
            confidence=Decimal("0.20"),
            probability_win=Decimal("0.20"),
            expected_return_pct=Decimal("0.01"),
            max_drawdown_pct=Decimal("0.10"),
        )
    )
    neg_high = CAIEScoringEngine.score(
        proposal(
            proposal_id="neg-high",
            confidence=Decimal("0.90"),
            probability_win=Decimal("0.20"),
            expected_return_pct=Decimal("0.01"),
            max_drawdown_pct=Decimal("0.10"),
        )
    )
    assert neg_low.expected_value_pct < 0
    assert neg_high.confidence_bonus == 0
    assert neg_high.total_score == neg_low.total_score


def test_higher_drawdown_reduces_score():
    low_risk = CAIEScoringEngine.score(proposal(proposal_id="low-risk", max_drawdown_pct=Decimal("0.03")))
    high_risk = CAIEScoringEngine.score(proposal(proposal_id="high-risk", max_drawdown_pct=Decimal("0.20")))
    assert low_risk.total_score > high_risk.total_score


def test_low_liquidity_reduces_score():
    liquid = CAIEScoringEngine.score(proposal(proposal_id="liquid", liquidity_score=Decimal("1.0")))
    illiquid = CAIEScoringEngine.score(proposal(proposal_id="illiquid", liquidity_score=Decimal("0.2")))
    assert liquid.total_score > illiquid.total_score


def test_poor_regime_alignment_reduces_score():
    aligned = CAIEScoringEngine.score(proposal(proposal_id="aligned", regime_alignment=Decimal("1.0")))
    poor = CAIEScoringEngine.score(proposal(proposal_id="poor", regime_alignment=Decimal("0.1")))
    assert aligned.total_score > poor.total_score


def test_score_remains_shadow_only():
    result = CAIEScoringEngine.score(proposal())
    assert result.status == "SHADOW_ONLY"
    assert not hasattr(result, "execution_allowed")
    assert not hasattr(CAIEScoringEngine, "place_order")


def test_invalid_proposal_fails_closed():
    bad = proposal(probability_win=Decimal("1.5"))
    with pytest.raises(ValueError, match="invalid opportunity proposal"):
        CAIEScoringEngine.score(bad)
