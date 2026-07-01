from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class SentimentIntelligenceEngine:
    """Interpret internal alert/recommendation sentiment without external calls."""

    NEGATIVE_TERMS = ("ERROR", "CRITICAL", "RED", "BLOCK", "FAIL", "PAUSE", "RISK_OFF")
    POSITIVE_TERMS = ("GREEN", "READY", "MAINTAIN", "RISK_ON", "FAVORABLE", "POSITIVE")

    def analyze(
        self,
        *,
        alerts: Sequence[Any] | None = None,
        recommendation_history: Sequence[Any] | None = None,
        runtime_warnings: Sequence[Any] | None = None,
        strategy_confidence_history: Sequence[Any] | None = None,
        market_regime: str | None = None,
    ) -> dict[str, Any]:
        rows = list(alerts or []) + list(recommendation_history or []) + list(runtime_warnings or []) + list(strategy_confidence_history or [])
        if not rows and not market_regime:
            return self._unavailable("sentiment_inputs_unavailable")

        positive = 0
        negative = 0
        reasons: list[str] = []
        for row in rows:
            text = self._text(row)
            upper = text.upper()
            if any(term in upper for term in self.NEGATIVE_TERMS):
                negative += 1
            if any(term in upper for term in self.POSITIVE_TERMS):
                positive += 1
        regime = str(market_regime or "").upper()
        if regime in {"BULL", "RISK_ON", "EXPANSION"}:
            positive += 1
            reasons.append("market_regime_risk_on")
        elif regime in {"BEAR", "RISK_OFF", "STRESS"}:
            negative += 1
            reasons.append("market_regime_risk_off")

        total = max(1, positive + negative)
        score = int(round(50 + ((positive - negative) / total) * 35))
        score = max(0, min(100, score))
        signal = "RISK_ON" if score >= 65 else "RISK_OFF" if score <= 35 else "NEUTRAL"
        if negative:
            reasons.append("negative_internal_signals_present")
        if positive:
            reasons.append("positive_internal_signals_present")

        return {
            "status": "OK" if rows else "PARTIAL",
            "sentiment_score": score,
            "sentiment_signal": signal,
            "sentiment_volatility": round(abs(positive - negative) / total, 6),
            "confidence": min(100, 40 + min(60, total * 10)),
            "reasons": sorted(set(reasons)) or ["sentiment_neutral"],
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _text(row: Any) -> str:
        if isinstance(row, Mapping):
            return " ".join(str(value) for value in row.values())
        return str(row)

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "sentiment_score": 0,
            "sentiment_signal": "DATA_UNAVAILABLE",
            "sentiment_volatility": None,
            "confidence": 0,
            "reasons": [reason],
            "advisory_only": True,
            "execution_allowed": False,
        }
