from __future__ import annotations

from typing import Any, Mapping

from .trade_quality_models import TradeQualityAssessment


class TradeQualityScoringEngineError(RuntimeError):
    """Fail-closed exception for trade quality scoring."""


class TradeQualityScoringEngine:
    """Scores trade candidates using deterministic multi-factor profitability inputs."""

    _ALLOWED_RECOMMENDATIONS = {"EXECUTE", "PREFERRED", "WATCH", "REJECT"}
    _REGIME_SCORES = {
        "TRENDING": 90.0,
        "BREAKOUT": 88.0,
        "RANGING": 62.0,
        "LOW_VOLATILITY": 60.0,
        "REVERSAL": 50.0,
        "HIGH_VOLATILITY": 44.0,
        "UNKNOWN": 35.0,
    }

    def score_candidates(self, candidates: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(candidates, list):
            raise TradeQualityScoringEngineError("candidates must be a list")
        return [self.score_candidate(candidate).to_dict() for candidate in candidates]

    def score_candidate(self, candidate: Mapping[str, Any]) -> TradeQualityAssessment:
        payload = self._normalize_candidate(candidate)

        factor_scores = {
            "market_regime": self._score_market_regime(payload),
            "strategy_intelligence": self._score_zero_to_one(payload.get("strategy_score")),
            "replay_confidence": self._score_zero_to_one(payload.get("replay_confidence")),
            "portfolio_concentration": self._score_inverted_risk(payload.get("concentration_risk")),
            "capital_allocation": self._score_capital_allocation(payload),
            "position_sizing": self._score_position_sizing(payload),
            "adaptive_exit_quality": self._score_exit_quality(payload),
            "risk_reward": self._score_risk_reward(payload),
        }

        weighted_score = (
            (factor_scores["market_regime"] * 0.13)
            + (factor_scores["strategy_intelligence"] * 0.16)
            + (factor_scores["replay_confidence"] * 0.12)
            + (factor_scores["portfolio_concentration"] * 0.12)
            + (factor_scores["capital_allocation"] * 0.12)
            + (factor_scores["position_sizing"] * 0.10)
            + (factor_scores["adaptive_exit_quality"] * 0.10)
            + (factor_scores["risk_reward"] * 0.15)
        )
        quality_score = round(max(0.0, min(100.0, weighted_score)), 8)
        confidence = round(max(0.0, min(1.0, quality_score / 100.0)), 8)
        recommendation = self._recommendation_for_score(quality_score)

        result = TradeQualityAssessment(
            trade_id=payload["trade_id"],
            symbol=payload["symbol"],
            asset_class=payload["asset_class"],
            quality_score=quality_score,
            confidence=confidence,
            recommendation=recommendation,
            factor_scores={key: round(float(value), 8) for key, value in factor_scores.items()},
            diagnostics={
                "weights": {
                    "market_regime": 0.13,
                    "strategy_intelligence": 0.16,
                    "replay_confidence": 0.12,
                    "portfolio_concentration": 0.12,
                    "capital_allocation": 0.12,
                    "position_sizing": 0.10,
                    "adaptive_exit_quality": 0.10,
                    "risk_reward": 0.15,
                },
                "market_regime": payload.get("market_regime", "UNKNOWN"),
                "exit_action": str(payload.get("exit_action") or "HOLD").strip().upper(),
            },
        )

        if result.recommendation not in self._ALLOWED_RECOMMENDATIONS:
            raise TradeQualityScoringEngineError("invalid recommendation generated")
        return result

    @staticmethod
    def _normalize_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise TradeQualityScoringEngineError("candidate must be a mapping")

        trade_id = str(candidate.get("trade_id") or "").strip()
        symbol = str(candidate.get("symbol") or "").strip().upper()
        asset_class = str(candidate.get("asset_class") or "").strip().upper()

        if not trade_id:
            raise TradeQualityScoringEngineError("trade_id must be non-empty")
        if not symbol:
            raise TradeQualityScoringEngineError("symbol must be non-empty")
        if not asset_class:
            raise TradeQualityScoringEngineError("asset_class must be non-empty")

        payload = dict(candidate)
        payload["trade_id"] = trade_id
        payload["symbol"] = symbol
        payload["asset_class"] = asset_class
        return payload

    def _score_market_regime(self, payload: Mapping[str, Any]) -> float:
        regime = str(payload.get("market_regime") or "UNKNOWN").strip().upper()
        return float(self._REGIME_SCORES.get(regime, self._REGIME_SCORES["UNKNOWN"]))

    @staticmethod
    def _score_zero_to_one(value: Any) -> float:
        if value is None:
            return 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise TradeQualityScoringEngineError("expected numeric 0..1 value") from exc
        return round(max(0.0, min(1.0, numeric)) * 100.0, 8)

    @staticmethod
    def _score_inverted_risk(value: Any) -> float:
        if value is None:
            return 100.0
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise TradeQualityScoringEngineError("expected numeric risk value") from exc
        clipped = max(0.0, min(1.0, numeric))
        return round((1.0 - clipped) * 100.0, 8)

    @staticmethod
    def _score_capital_allocation(payload: Mapping[str, Any]) -> float:
        weight = payload.get("allocation_weight")
        if weight is None:
            amount = payload.get("allocation_amount")
            capital = payload.get("available_capital")
            if amount is None or capital is None:
                return 0.0
            try:
                amount_value = float(amount)
                capital_value = float(capital)
            except (TypeError, ValueError) as exc:
                raise TradeQualityScoringEngineError("allocation amount/capital must be numeric") from exc
            if capital_value <= 0.0:
                raise TradeQualityScoringEngineError("available_capital must be positive")
            weight_value = amount_value / capital_value
        else:
            try:
                weight_value = float(weight)
            except (TypeError, ValueError) as exc:
                raise TradeQualityScoringEngineError("allocation_weight must be numeric") from exc

        clipped = max(0.0, min(0.35, weight_value))
        return round((clipped / 0.35) * 100.0, 8)

    @staticmethod
    def _score_position_sizing(payload: Mapping[str, Any]) -> float:
        position_size = payload.get("recommended_position_size")
        if position_size is None:
            return 0.0
        try:
            size_value = float(position_size)
        except (TypeError, ValueError) as exc:
            raise TradeQualityScoringEngineError("recommended_position_size must be numeric") from exc
        if size_value <= 0.0:
            return 0.0

        allocation_amount = payload.get("allocation_amount")
        if allocation_amount is None:
            return 100.0

        try:
            allocation_value = float(allocation_amount)
        except (TypeError, ValueError) as exc:
            raise TradeQualityScoringEngineError("allocation_amount must be numeric") from exc
        if allocation_value <= 0.0:
            return 0.0

        ratio = max(0.0, min(1.0, size_value / allocation_value))
        return round(ratio * 100.0, 8)

    @staticmethod
    def _score_exit_quality(payload: Mapping[str, Any]) -> float:
        action = str(payload.get("exit_action") or "HOLD").strip().upper()
        confidence = payload.get("exit_confidence", 0.5)
        try:
            confidence_value = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError) as exc:
            raise TradeQualityScoringEngineError("exit_confidence must be numeric") from exc

        baseline = {
            "HOLD": 75.0,
            "TRAIL": 82.0,
            "TAKE_PROFIT": 65.0,
            "REDUCE": 55.0,
            "TIME_EXIT": 45.0,
            "STOP_LOSS": 20.0,
        }.get(action, 50.0)

        adjusted = baseline * 0.7 + (confidence_value * 100.0 * 0.3)
        return round(max(0.0, min(100.0, adjusted)), 8)

    @staticmethod
    def _score_risk_reward(payload: Mapping[str, Any]) -> float:
        ratio = payload.get("risk_reward")
        if ratio is None:
            ratio = payload.get("risk_reward_ratio")
        if ratio is None:
            return 0.0
        try:
            ratio_value = float(ratio)
        except (TypeError, ValueError) as exc:
            raise TradeQualityScoringEngineError("risk_reward must be numeric") from exc

        if ratio_value <= 0.0:
            return 0.0
        if ratio_value >= 3.0:
            return 100.0
        if ratio_value >= 2.0:
            return 85.0
        if ratio_value >= 1.0:
            return 65.0
        if ratio_value >= 0.5:
            return 40.0
        return 20.0

    @staticmethod
    def _recommendation_for_score(score: float) -> str:
        if score >= 80.0:
            return "EXECUTE"
        if score >= 65.0:
            return "PREFERRED"
        if score >= 45.0:
            return "WATCH"
        return "REJECT"
