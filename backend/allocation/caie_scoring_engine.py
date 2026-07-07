from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CAIEScoringEngine:
    """Advisory-only CAIE scoring for already-validated opportunity proposals."""

    def score(
        self,
        validated_input: Mapping[str, Any] | None,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(validated_input, Mapping):
            return self._fail_closed("validated_input_must_be_mapping")

        if bool(validated_input.get("valid")) is not True:
            return self._fail_closed("proposal_not_validated")

        normalized = validated_input.get("normalized")
        if not isinstance(normalized, Mapping):
            return self._fail_closed("validated_input_missing_normalized_payload")

        context_payload = context or {}
        if not isinstance(context_payload, Mapping):
            return self._fail_closed("context_must_be_mapping")

        try:
            probability = float(normalized["probability"])
            confidence = float(normalized["confidence"])
            expected_drawdown_pct = float(normalized["expected_drawdown_pct"])
            risk_score = float(normalized["risk_score"])
            requested_capital = float(normalized["requested_capital"])
        except (KeyError, TypeError, ValueError):
            return self._fail_closed("validated_payload_numeric_fields_invalid")

        try:
            liquidity_score = float(context_payload.get("liquidity_score", 1.0))
            regime_alignment = float(context_payload.get("regime_alignment", 1.0))
        except (TypeError, ValueError):
            return self._fail_closed("context_numeric_fields_invalid")

        if not self._in_range(probability, 0.0, 1.0):
            return self._fail_closed("probability_out_of_range")
        if not self._in_range(confidence, 0.0, 1.0):
            return self._fail_closed("confidence_out_of_range")
        if not self._in_range(expected_drawdown_pct, 0.0, 1.0):
            return self._fail_closed("expected_drawdown_pct_out_of_range")
        if not self._in_range(risk_score, 0.0, 100.0):
            return self._fail_closed("risk_score_out_of_range")
        if requested_capital <= 0.0:
            return self._fail_closed("requested_capital_not_positive")
        if not self._in_range(liquidity_score, 0.0, 1.0):
            return self._fail_closed("liquidity_score_out_of_range")
        if not self._in_range(regime_alignment, 0.0, 1.0):
            return self._fail_closed("regime_alignment_out_of_range")

        expected_value = probability - expected_drawdown_pct
        positive_ev = expected_value > 0.0

        confidence_contribution = (confidence * expected_value * 20.0) if positive_ev else 0.0
        capital_efficiency = 1.0 / (1.0 + (requested_capital / 10000.0))
        capital_efficiency_contribution = (capital_efficiency * expected_value * 30.0) if positive_ev else 0.0

        ev_contribution = expected_value * 100.0
        liquidity_contribution = liquidity_score * 15.0
        regime_contribution = regime_alignment * 15.0

        drawdown_penalty = expected_drawdown_pct * 35.0
        risk_penalty = (risk_score / 100.0) * 25.0

        score = (
            50.0
            + ev_contribution
            + confidence_contribution
            + capital_efficiency_contribution
            + liquidity_contribution
            + regime_contribution
            - drawdown_penalty
            - risk_penalty
        )

        return {
            "valid": True,
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
            "score": round(score, 6),
            "components": {
                "expected_value": round(expected_value, 6),
                "ev_contribution": round(ev_contribution, 6),
                "confidence_contribution": round(confidence_contribution, 6),
                "capital_efficiency": round(capital_efficiency, 6),
                "capital_efficiency_contribution": round(capital_efficiency_contribution, 6),
                "liquidity_contribution": round(liquidity_contribution, 6),
                "regime_contribution": round(regime_contribution, 6),
                "drawdown_penalty": round(drawdown_penalty, 6),
                "risk_penalty": round(risk_penalty, 6),
            },
            "reason": "score_computed",
        }

    @staticmethod
    def _in_range(value: float, minimum: float, maximum: float) -> bool:
        return minimum <= value <= maximum

    @staticmethod
    def _fail_closed(reason: str) -> dict[str, Any]:
        return {
            "valid": False,
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
            "score": None,
            "components": None,
            "reason": reason,
        }


def score_validated_opportunity(
    validated_input: Mapping[str, Any] | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return CAIEScoringEngine().score(validated_input, context=context)
