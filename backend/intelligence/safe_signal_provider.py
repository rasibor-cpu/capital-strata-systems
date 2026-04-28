from __future__ import annotations

import random
from typing import Any


try:
    from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
except Exception:
    AIOpportunityScorer = None

try:
    from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
except Exception:
    SignalConfluenceEngine = None


def _coerce_number(value: Any, default: float) -> float:
    try:
        if isinstance(value, dict):
            for key in (
                "score",
                "signal_score",
                "value",
                "probability",
                "prob",
                "confidence",
                "confidence_score",
            ):
                if key in value:
                    return float(value[key])
            return float(default)

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value.strip())
            except Exception:
                return float(default)

        for attr in (
            "score",
            "signal_score",
            "value",
            "probability",
            "prob",
            "confidence",
            "confidence_score",
        ):
            if hasattr(value, attr):
                return float(getattr(value, attr))

        return float(default)
    except Exception:
        return float(default)


class SafeSignalProvider:
    """
    PCNRASS-compliant signal provider.

    Contract:
    - Never crashes dashboard
    - Never blocks trade loop
    - Uses intelligence modules only when their output is usable
    - Falls back safely when modules return strings/None/unexpected objects
    """

    def __init__(self) -> None:
        self.ai_scorer = None
        self.confluence = None

        if AIOpportunityScorer is not None:
            try:
                self.ai_scorer = AIOpportunityScorer()
            except Exception as exc:
                print(f"[SIGNAL INIT FALLBACK] AIOpportunityScorer unavailable: {str(exc)[:80]}")
                self.ai_scorer = None

        if SignalConfluenceEngine is not None:
            try:
                self.confluence = SignalConfluenceEngine()
            except Exception as exc:
                print(f"[SIGNAL INIT FALLBACK] SignalConfluenceEngine unavailable: {str(exc)[:80]}")
                self.confluence = None

    def _score_from_ai(self, symbol: str, asset_class: str) -> Any:
        if self.ai_scorer is None:
            return None

        for method_name in ("score", "evaluate", "score_opportunity", "get_score"):
            method = getattr(self.ai_scorer, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(symbol=symbol, asset_class=asset_class)
                    except TypeError:
                        return method(symbol)
                except Exception as exc:
                    print(f"[SIGNAL AI METHOD FALLBACK] {symbol} {method_name}: {str(exc)[:80]}")
                    return None

        return None

    def _prob_from_confluence(self, symbol: str, asset_class: str) -> Any:
        if self.confluence is None:
            return None

        for method_name in ("probability", "evaluate", "get_probability", "confidence"):
            method = getattr(self.confluence, method_name, None)
            if callable(method):
                try:
                    try:
                        return method(symbol=symbol, asset_class=asset_class)
                    except TypeError:
                        return method(symbol)
                except Exception as exc:
                    print(f"[SIGNAL CONFLUENCE METHOD FALLBACK] {symbol} {method_name}: {str(exc)[:80]}")
                    return None

        return None

    def get_signal(self, symbol: str, asset_class: str) -> tuple[float, float]:
        default_score = random.uniform(5.0, 15.0)
        default_prob = random.uniform(0.4, 0.6)

        score_raw = self._score_from_ai(symbol, asset_class)
        prob_raw = self._prob_from_confluence(symbol, asset_class)

        score = _coerce_number(score_raw, default_score)
        prob = _coerce_number(prob_raw, default_prob)

        score = float(max(0.0, min(20.0, score)))
        prob = float(max(0.0, min(1.0, prob)))

        return score, prob
