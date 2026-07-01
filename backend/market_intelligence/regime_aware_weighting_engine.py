from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class RegimeAwareWeightingEngine:
    """Build advisory-only market intelligence weights from regime context."""

    FACTORS = ("technical", "fundamental", "sentiment", "quantitative")
    SCORE_KEYS = {
        "technical": "technical_score",
        "fundamental": "fundamental_quality_score",
        "sentiment": "sentiment_score",
        "quantitative": "alpha_score",
    }
    SAFE_BALANCED_WEIGHTS = {
        "technical": 25.0,
        "fundamental": 25.0,
        "sentiment": 25.0,
        "quantitative": 25.0,
    }

    def evaluate(
        self,
        *,
        market_regime: Mapping[str, Any] | None = None,
        portfolio_lifecycle: Mapping[str, Any] | None = None,
        technical: Mapping[str, Any] | None = None,
        fundamental: Mapping[str, Any] | None = None,
        sentiment: Mapping[str, Any] | None = None,
        quantitative: Mapping[str, Any] | None = None,
        policy_profile: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        components = {
            "technical": technical,
            "fundamental": fundamental,
            "sentiment": sentiment,
            "quantitative": quantitative,
        }
        reasons: list[str] = []
        regime = self._regime_name(market_regime)
        weights = self._base_weights(regime, reasons)
        weights = self._apply_policy_profile(weights, policy_profile, reasons)

        available = {
            name
            for name, payload in components.items()
            if self._component_available(name, payload)
        }
        missing = [name for name in self.FACTORS if name not in available]
        if missing:
            reasons.extend(f"{name}_component_unavailable" for name in missing)

        confidence_adjustment = -10 * len(missing)
        if len(available) == len(self.FACTORS) and regime != "UNKNOWN":
            confidence_adjustment += 5

        lifecycle_state = self._portfolio_state(portfolio_lifecycle)
        if lifecycle_state in {"NO_PORTFOLIO", "STARTUP", "INITIALIZING", "UNKNOWN"}:
            confidence_adjustment -= 10
            reasons.append(f"portfolio_context_{lifecycle_state.lower()}")

        if available:
            adjusted = {
                name: (weights[name] if name in available else 0.0)
                for name in self.FACTORS
            }
            weights = self._normalize(adjusted)
            status = "OK" if len(available) == len(self.FACTORS) else "PARTIAL"
        else:
            weights = self._normalize(weights)
            status = "DATA UNAVAILABLE"
            confidence_adjustment = -100
            reasons.append("market_intelligence_components_unavailable")

        confidence_adjustment = max(-100, min(100, int(round(confidence_adjustment))))
        return {
            "status": status,
            "regime": regime,
            "weights": weights,
            "weight_sum": round(sum(weights.values()), 6),
            "confidence_adjustment": confidence_adjustment,
            "reasons": sorted(set(reasons)) or ["balanced_regime_weighting"],
            "advisory_only": True,
            "execution_allowed": False,
        }

    @classmethod
    def _component_available(cls, name: str, payload: Mapping[str, Any] | None) -> bool:
        if not isinstance(payload, Mapping):
            return False
        if str(payload.get("status", "")).upper() == "DATA UNAVAILABLE":
            return False
        return payload.get(cls.SCORE_KEYS[name]) is not None

    @staticmethod
    def _regime_name(payload: Mapping[str, Any] | None) -> str:
        if not isinstance(payload, Mapping):
            return "UNKNOWN"
        for key in ("detected_regime", "market_regime", "regime", "runtime_state_status"):
            value = str(payload.get(key, "")).strip().upper()
            if value:
                return value
        return "UNKNOWN"

    def _base_weights(self, regime: str, reasons: list[str]) -> dict[str, float]:
        if regime in {"TRENDING", "TRENDING_UP", "TRENDING_DOWN", "BREAKOUT", "MOMENTUM", "RISK_ON"}:
            reasons.append("trending_regime_increases_technical_quantitative")
            return {"technical": 35.0, "fundamental": 15.0, "sentiment": 15.0, "quantitative": 35.0}
        if regime in {"HIGH_VOLATILITY", "VOLATILE", "CORRELATION_STRESS", "VOLATILITY_SPIKE"}:
            reasons.append("high_volatility_regime_increases_sentiment_risk_awareness")
            return {"technical": 20.0, "fundamental": 20.0, "sentiment": 35.0, "quantitative": 25.0}
        if regime in {"RISK_OFF", "BEAR", "BEARISH", "DEFENSIVE", "MACRO", "MACRO_STRESS", "STRESS"}:
            reasons.append("macro_risk_off_regime_increases_fundamental_sentiment")
            return {"technical": 15.0, "fundamental": 35.0, "sentiment": 35.0, "quantitative": 15.0}
        reasons.append("unknown_regime_safe_balanced_default")
        return dict(self.SAFE_BALANCED_WEIGHTS)

    def _apply_policy_profile(
        self,
        weights: Mapping[str, float],
        policy_profile: Mapping[str, Any] | None,
        reasons: list[str],
    ) -> dict[str, float]:
        adjusted = dict(weights)
        if not isinstance(policy_profile, Mapping):
            return adjusted
        profile = str(
            policy_profile.get("active_profile")
            or policy_profile.get("profile")
            or policy_profile.get("name")
            or ""
        ).upper()
        if profile in {"DEFENSIVE", "CAPITAL_PRESERVATION", "CONSERVATIVE"}:
            adjusted["fundamental"] += 5.0
            adjusted["sentiment"] += 5.0
            adjusted["technical"] = max(0.0, adjusted["technical"] - 5.0)
            adjusted["quantitative"] = max(0.0, adjusted["quantitative"] - 5.0)
            reasons.append("defensive_policy_profile_weight_adjustment")
        elif profile in {"GROWTH", "AGGRESSIVE", "OPPORTUNISTIC"}:
            adjusted["technical"] += 5.0
            adjusted["quantitative"] += 5.0
            adjusted["fundamental"] = max(0.0, adjusted["fundamental"] - 5.0)
            adjusted["sentiment"] = max(0.0, adjusted["sentiment"] - 5.0)
            reasons.append("growth_policy_profile_weight_adjustment")
        return self._normalize(adjusted)

    @staticmethod
    def _portfolio_state(payload: Mapping[str, Any] | None) -> str:
        if not isinstance(payload, Mapping):
            return "UNKNOWN"
        for key in ("portfolio_lifecycle_state", "lifecycle_state", "portfolio_state", "status"):
            value = str(payload.get(key, "")).strip().upper()
            if value:
                return value
        return "UNKNOWN"

    def _normalize(self, weights: Mapping[str, float]) -> dict[str, float]:
        positive = {
            name: max(0.0, float(weights.get(name, 0.0)))
            for name in self.FACTORS
        }
        total = sum(positive.values())
        if total <= 0:
            positive = dict(self.SAFE_BALANCED_WEIGHTS)
            total = 100.0
        normalized = {
            name: round((value / total) * 100.0, 6)
            for name, value in positive.items()
        }
        residual = round(100.0 - sum(normalized.values()), 6)
        if residual:
            target = max(normalized, key=normalized.get)
            normalized[target] = round(normalized[target] + residual, 6)
        return normalized
