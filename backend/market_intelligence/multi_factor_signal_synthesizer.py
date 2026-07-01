from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class MultiFactorSignalSynthesizer:
    """Combine advisory-only market intelligence components."""

    SCORE_KEYS = {
        "technical": "technical_score",
        "fundamental": "fundamental_quality_score",
        "sentiment": "sentiment_score",
        "quantitative": "alpha_score",
    }
    SIGNAL_KEYS = {
        "technical": "technical_signal",
        "fundamental": "fundamental_signal",
        "sentiment": "sentiment_signal",
        "quantitative": "quantitative_signal",
    }

    def synthesize(
        self,
        *,
        technical: Mapping[str, Any] | None = None,
        fundamental: Mapping[str, Any] | None = None,
        sentiment: Mapping[str, Any] | None = None,
        quantitative: Mapping[str, Any] | None = None,
        market_regime: Mapping[str, Any] | None = None,
        portfolio_decision: Mapping[str, Any] | None = None,
        regime_weights: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        components = {
            "technical": technical,
            "fundamental": fundamental,
            "sentiment": sentiment,
            "quantitative": quantitative,
        }
        available: dict[str, Mapping[str, Any]] = {
            name: payload for name, payload in components.items() if isinstance(payload, Mapping) and str(payload.get("status", "")).upper() != "DATA UNAVAILABLE"
        }
        if not available:
            return self._unavailable("multi_factor_components_unavailable")

        component_scores: dict[str, int] = {}
        component_signals: dict[str, str] = {}
        reasons: list[str] = []
        for name, payload in components.items():
            if not isinstance(payload, Mapping):
                component_signals[name] = "DATA_UNAVAILABLE"
                reasons.append(f"{name}_missing")
                continue
            component_scores[name] = self._score(payload.get(self.SCORE_KEYS[name]))
            component_signals[name] = str(payload.get(self.SIGNAL_KEYS[name], "DATA_UNAVAILABLE")).upper()
            reasons.extend(str(item) for item in payload.get("reasons", []) if str(item).strip())

        weights, weighting_reasons, confidence_adjustment = self._resolve_weights(regime_weights)
        score = (
            int(round(sum(component_scores.get(name, 0) * (weights.get(name, 0.0) / 100.0) for name in self.SCORE_KEYS)))
            if component_scores
            else 0
        )
        conflicts = self._conflict_count(component_signals)
        missing = 4 - len(available)
        confidence = max(0, min(100, int(round(100 - missing * 15 - conflicts * 12))))
        confidence = max(0, min(100, confidence + confidence_adjustment))
        reasons.extend(weighting_reasons)

        decision_status = str((portfolio_decision or {}).get("overall_status", "")).upper() if isinstance(portfolio_decision, Mapping) else ""
        if decision_status == "RED":
            reasons.append("portfolio_decision_red_context")
            confidence = min(confidence, 50)

        signal = self._signal(score)
        status = "OK" if len(available) == 4 else "PARTIAL"
        return {
            "status": status,
            "multi_factor_score": score,
            "multi_factor_signal": signal,
            "component_scores": component_scores,
            "component_signals": component_signals,
            "regime_weights": weights,
            "weighting_confidence_adjustment": confidence_adjustment,
            "weighting_reasons": sorted(set(weighting_reasons)),
            "confidence": confidence,
            "reasons": sorted(set(reasons)) or ["multi_factor_neutral"],
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _score(value: Any) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _conflict_count(signals: Mapping[str, str]) -> int:
        positives = {"BULLISH", "POSITIVE", "RISK_ON", "FAVORABLE", "STRONG_POSITIVE"}
        negatives = {"BEARISH", "NEGATIVE", "RISK_OFF", "UNFAVORABLE", "STRONG_NEGATIVE"}
        has_positive = any(value in positives for value in signals.values())
        has_negative = any(value in negatives for value in signals.values())
        return 1 if has_positive and has_negative else 0

    @staticmethod
    def _signal(score: int) -> str:
        if score >= 80:
            return "STRONG_POSITIVE"
        if score >= 60:
            return "POSITIVE"
        if score <= 20:
            return "STRONG_NEGATIVE"
        if score <= 40:
            return "NEGATIVE"
        return "NEUTRAL"

    def _resolve_weights(self, payload: Mapping[str, Any] | None) -> tuple[dict[str, float], list[str], int]:
        if isinstance(payload, Mapping) and isinstance(payload.get("weights"), Mapping):
            weights = self._normalize_weights(payload.get("weights"))
            reasons = [str(item) for item in payload.get("reasons", []) if str(item).strip()]
            adjustment = self._int(payload.get("confidence_adjustment"))
            return weights, reasons or ["regime_aware_weighting_applied"], max(-100, min(100, adjustment))
        return (
            {name: 25.0 for name in self.SCORE_KEYS},
            ["equal_weight_fallback"],
            0,
        )

    def _normalize_weights(self, raw: Mapping[str, Any]) -> dict[str, float]:
        weights = {
            name: max(0.0, self._float(raw.get(name, 0.0)))
            for name in self.SCORE_KEYS
        }
        total = sum(weights.values())
        if total <= 0:
            weights = {name: 25.0 for name in self.SCORE_KEYS}
            total = 100.0
        normalized = {
            name: round((value / total) * 100.0, 6)
            for name, value in weights.items()
        }
        residual = round(100.0 - sum(normalized.values()), 6)
        if residual:
            target = max(normalized, key=normalized.get)
            normalized[target] = round(normalized[target] + residual, 6)
        return normalized

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "multi_factor_score": 0,
            "multi_factor_signal": "DATA_UNAVAILABLE",
            "component_scores": {},
            "component_signals": {},
            "regime_weights": {name: 25.0 for name in MultiFactorSignalSynthesizer.SCORE_KEYS},
            "weighting_confidence_adjustment": 0,
            "weighting_reasons": ["equal_weight_fallback"],
            "confidence": 0,
            "reasons": [reason],
            "advisory_only": True,
            "execution_allowed": False,
        }
