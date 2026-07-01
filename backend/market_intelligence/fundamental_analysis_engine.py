from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class FundamentalAnalysisEngine:
    """Generic internal-metadata fundamental quality scoring."""

    def evaluate(self, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = metadata if isinstance(metadata, Mapping) else {}
        if not data:
            return self._unavailable("fundamental_metadata_unavailable")

        reasons: list[str] = []
        score = 50.0
        meaningful = False

        asset_class = str(data.get("asset_class", data.get("class", ""))).upper()
        instrument_type = str(data.get("instrument_type", data.get("type", ""))).upper()
        if asset_class or instrument_type or data.get("symbol"):
            meaningful = True
            reasons.append("instrument_metadata_available")

        valuation = data.get("valuation_score")
        if valuation is not None:
            score += (self._bounded_float(valuation) - 50.0) * 0.5
            meaningful = True
            reasons.append("valuation_score_available")
        pe_ratio = self._float(data.get("pe_ratio"))
        if pe_ratio is not None:
            meaningful = True
            if pe_ratio <= 15:
                score += 12
            elif pe_ratio >= 35:
                score -= 12
            reasons.append("pe_ratio_available")

        macro = self._float(data.get("macro_sensitivity", data.get("rate_sensitivity")))
        if macro is not None:
            meaningful = True
            score -= min(15.0, abs(macro) * 10.0)
            reasons.append("macro_sensitivity_available")
        balance = self._float(data.get("balance_quality", data.get("quality_score")))
        if balance is not None:
            meaningful = True
            score += (max(0.0, min(100.0, balance)) - 50.0) * 0.35
            reasons.append("balance_quality_available")

        if asset_class in {"CRYPTO", "FX", "FUTURES", "OPTIONS"} and valuation is None and pe_ratio is None:
            reasons.append("traditional_fundamentals_limited_for_asset_class")

        if not meaningful:
            return self._unavailable("fundamental_metadata_unavailable")

        bounded = max(0, min(100, int(round(score))))
        valuation_status = "ATTRACTIVE" if bounded >= 65 else "EXPENSIVE" if bounded <= 35 else "FAIR"
        signal = "POSITIVE" if bounded >= 65 else "NEGATIVE" if bounded <= 35 else "NEUTRAL"
        status = "OK" if any(key in data for key in ("valuation_score", "pe_ratio", "balance_quality", "quality_score")) else "PARTIAL"
        return {
            "status": status,
            "fundamental_quality_score": bounded,
            "valuation_status": valuation_status,
            "macro_sensitivity": macro,
            "balance_quality": balance,
            "fundamental_signal": signal,
            "reasons": sorted(set(reasons)),
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _bounded_float(value: Any) -> float:
        try:
            return max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            return 50.0

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "fundamental_quality_score": 0,
            "valuation_status": "UNKNOWN",
            "macro_sensitivity": None,
            "balance_quality": None,
            "fundamental_signal": "DATA_UNAVAILABLE",
            "reasons": [reason],
            "advisory_only": True,
            "execution_allowed": False,
        }
