from __future__ import annotations

from copy import deepcopy

from backend.allocation.caie_scoring_engine import score_validated_opportunity
from backend.allocation.opportunity_validator import validate_opportunity_proposal


def _proposal(
    *,
    probability: float = 0.7,
    confidence: float = 0.8,
    expected_drawdown_pct: float = 0.2,
    risk_score: float = 35.0,
    requested_capital: float = 2000.0,
) -> dict:
    return {
        "proposal_id": "caie-155b",
        "symbol": "BTC-USD",
        "asset_class": "CRYPTO",
        "probability": probability,
        "confidence": confidence,
        "expected_drawdown_pct": expected_drawdown_pct,
        "risk_score": risk_score,
        "requested_capital": requested_capital,
    }


def _validated(payload: dict) -> dict:
    result = validate_opportunity_proposal(payload)
    assert result["valid"] is True
    return result


def test_phase155b_positive_ev_scores_higher_than_negative_ev() -> None:
    positive = _validated(_proposal(probability=0.75, expected_drawdown_pct=0.2))
    negative = _validated(_proposal(probability=0.2, expected_drawdown_pct=0.75))

    positive_score = score_validated_opportunity(positive)
    negative_score = score_validated_opportunity(negative)

    assert positive_score["score"] > negative_score["score"]


def test_phase155b_high_confidence_only_boosts_when_ev_is_positive() -> None:
    pos_low_conf = score_validated_opportunity(
        _validated(_proposal(probability=0.8, expected_drawdown_pct=0.2, confidence=0.2))
    )
    pos_high_conf = score_validated_opportunity(
        _validated(_proposal(probability=0.8, expected_drawdown_pct=0.2, confidence=0.95))
    )

    neg_low_conf = score_validated_opportunity(
        _validated(_proposal(probability=0.2, expected_drawdown_pct=0.8, confidence=0.2))
    )
    neg_high_conf = score_validated_opportunity(
        _validated(_proposal(probability=0.2, expected_drawdown_pct=0.8, confidence=0.95))
    )

    assert pos_high_conf["score"] > pos_low_conf["score"]
    assert neg_high_conf["score"] == neg_low_conf["score"]


def test_phase155b_high_drawdown_and_risk_reduce_score() -> None:
    safer = score_validated_opportunity(
        _validated(_proposal(expected_drawdown_pct=0.1, risk_score=20.0))
    )
    riskier = score_validated_opportunity(
        _validated(_proposal(expected_drawdown_pct=0.5, risk_score=90.0))
    )

    assert safer["score"] > riskier["score"]


def test_phase155b_low_liquidity_reduces_score() -> None:
    validated = _validated(_proposal())

    liquid = score_validated_opportunity(validated, context={"liquidity_score": 1.0, "regime_alignment": 1.0})
    illiquid = score_validated_opportunity(validated, context={"liquidity_score": 0.1, "regime_alignment": 1.0})

    assert liquid["score"] > illiquid["score"]


def test_phase155b_poor_regime_alignment_reduces_score() -> None:
    validated = _validated(_proposal())

    aligned = score_validated_opportunity(validated, context={"liquidity_score": 1.0, "regime_alignment": 1.0})
    misaligned = score_validated_opportunity(validated, context={"liquidity_score": 1.0, "regime_alignment": 0.1})

    assert aligned["score"] > misaligned["score"]


def test_phase155b_capital_efficiency_improves_score_when_ev_positive() -> None:
    efficient = score_validated_opportunity(
        _validated(_proposal(probability=0.8, expected_drawdown_pct=0.2, requested_capital=1000.0))
    )
    inefficient = score_validated_opportunity(
        _validated(_proposal(probability=0.8, expected_drawdown_pct=0.2, requested_capital=9000.0))
    )

    assert efficient["score"] > inefficient["score"]


def test_phase155b_invalid_or_unvalidated_inputs_fail_closed() -> None:
    invalid_type = score_validated_opportunity(None)
    not_validated = score_validated_opportunity({"valid": False, "normalized": {}})
    invalid_context = score_validated_opportunity(
        _validated(_proposal()),
        context={"liquidity_score": 5.0, "regime_alignment": 1.0},
    )

    assert invalid_type["valid"] is False
    assert invalid_type["score"] is None
    assert not_validated["valid"] is False
    assert not_validated["score"] is None
    assert invalid_context["valid"] is False
    assert invalid_context["score"] is None


def test_phase155b_scoring_output_is_deterministic() -> None:
    validated = _validated(_proposal())
    context = {"liquidity_score": 0.65, "regime_alignment": 0.4}

    first = score_validated_opportunity(validated, context=context)
    second = score_validated_opportunity(deepcopy(validated), context=deepcopy(context))

    assert first == second


def test_phase155b_output_is_advisory_shadow_only() -> None:
    result = score_validated_opportunity(_validated(_proposal()))

    assert result["valid"] is True
    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"
