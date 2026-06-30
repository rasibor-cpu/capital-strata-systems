from __future__ import annotations

from typing import Any, Mapping

from backend.portfolio.constants import (
    CANONICAL_REGIMES,
    LEGACY_REGIME_ALIASES,
    REGIME_CORRELATION_STRESS,
    REGIME_HIGH_VOLATILITY,
    REGIME_LOW_VOLATILITY,
    REGIME_RANGING,
    REGIME_TRENDING_DOWN,
    REGIME_TRENDING_UP,
    REGIME_UNKNOWN,
)
from backend.portfolio.utils import normalize_allocations, safe_float


class RegimeAwareAllocationError(RuntimeError):
    """Fail-closed exception for regime-aware allocation analysis."""


class RegimeAwareAllocationEngine:
    """Advisory-only allocation adjustment by market regime."""

    HIGH_RISK_CLASSES = {"CRYPTO", "OPTIONS", "FUTURES", "SMALL_CAP", "LEVERAGED_ETF"}

    def adjust(
        self,
        base_allocations: Mapping[str, Any] | None,
        regime_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if base_allocations is None or not isinstance(base_allocations, Mapping):
            return self._fail_closed("base_allocations_unavailable")
        if not base_allocations:
            return self._limited_no_allocations(regime_context)

        base = normalize_allocations(base_allocations)
        if not base:
            return self._fail_closed("base_allocations_invalid")

        context = regime_context if isinstance(regime_context, Mapping) else {}
        regime = self._canonical_regime(context.get("detected_regime", context.get("market_regime", REGIME_UNKNOWN)))

        drawdown = safe_float(context.get("max_drawdown", context.get("drawdown", 0.0)))
        downside_ok = drawdown <= 0.08 and str(context.get("risk_status", "GREEN")).upper() != "RED"
        adjusted = dict(base)
        reasons: list[str] = []

        if regime == REGIME_HIGH_VOLATILITY:
            adjusted = self._shift_to_cash(adjusted, 15.0)
            adjusted = self._reduce_high_risk(adjusted, 0.80)
            bias = "DEFENSIVE"
            reasons.append("High volatility increases defensive reserve and reduces high-risk classes.")
        elif regime == REGIME_CORRELATION_STRESS:
            adjusted = self._shift_to_cash(adjusted, 15.0)
            adjusted = self._reduce_high_risk(adjusted, 0.75)
            bias = "DEFENSIVE"
            reasons.append("Correlation stress increases defensive reserve and reduces high-risk classes.")
        elif regime == REGIME_TRENDING_DOWN:
            adjusted = self._shift_to_cash(adjusted, 12.5)
            adjusted = self._reduce_high_risk(adjusted, 0.85)
            bias = "DEFENSIVE"
            reasons.append("Trending down regime requires defensive allocation posture.")
        elif regime == REGIME_TRENDING_UP and downside_ok:
            adjusted = self._shift_from_cash(adjusted, 5.0)
            bias = "GROWTH"
            reasons.append("Trending up regime with acceptable downside supports selective risk-on allocation.")
        elif regime == REGIME_TRENDING_UP:
            adjusted = self._shift_to_cash(adjusted, 5.0)
            bias = "BALANCED"
            reasons.append("Trending up regime has unacceptable downside metrics, so allocation remains cautious.")
        elif regime == REGIME_LOW_VOLATILITY:
            bias = "BALANCED"
            reasons.append("Low volatility supports balanced allocation posture.")
        elif regime == REGIME_RANGING:
            adjusted = self._shift_to_cash(adjusted, 5.0)
            bias = "BALANCED"
            reasons.append("Ranging regime keeps modest defensive reserve.")
        else:
            adjusted = self._shift_to_cash(adjusted, 10.0)
            bias = "DEFENSIVE"
            reasons.append("Unknown regime remains conservative.")

        adjusted = normalize_allocations(adjusted)
        return {
            "status": "OK",
            "base_allocations": base,
            "regime_adjusted_allocations": adjusted,
            "detected_regime": regime,
            "allocation_bias": bias,
            "reasons": reasons,
            "advisory_only": True,
        }

    @staticmethod
    def _canonical_regime(value: Any) -> str:
        regime = str(value or REGIME_UNKNOWN).strip().upper()
        regime = LEGACY_REGIME_ALIASES.get(regime, regime)
        return regime if regime in CANONICAL_REGIMES else REGIME_UNKNOWN

    def _shift_to_cash(self, allocations: dict[str, float], shift: float) -> dict[str, float]:
        adjusted = dict(allocations)
        non_cash_keys = [key for key in sorted(adjusted.keys()) if key != "CASH" and adjusted[key] > 0.0]
        if not non_cash_keys:
            adjusted["CASH"] = 100.0
            return adjusted
        total_non_cash = sum(adjusted[key] for key in non_cash_keys)
        actual_shift = min(shift, total_non_cash)
        for key in non_cash_keys:
            adjusted[key] = max(0.0, adjusted[key] - actual_shift * (adjusted[key] / total_non_cash))
        adjusted["CASH"] = adjusted.get("CASH", 0.0) + actual_shift
        return adjusted

    def _shift_from_cash(self, allocations: dict[str, float], shift: float) -> dict[str, float]:
        adjusted = dict(allocations)
        cash = adjusted.get("CASH", 0.0)
        actual_shift = min(shift, cash)
        if actual_shift <= 0.0:
            return adjusted
        growth_keys = [key for key in sorted(adjusted.keys()) if key != "CASH"]
        if not growth_keys:
            return adjusted
        adjusted["CASH"] = cash - actual_shift
        per_key = actual_shift / len(growth_keys)
        for key in growth_keys:
            adjusted[key] += per_key
        return adjusted

    def _reduce_high_risk(self, allocations: dict[str, float], multiplier: float) -> dict[str, float]:
        adjusted = dict(allocations)
        released = 0.0
        for key in sorted(adjusted.keys()):
            if key in self.HIGH_RISK_CLASSES:
                old = adjusted[key]
                adjusted[key] = old * multiplier
                released += old - adjusted[key]
        adjusted["CASH"] = adjusted.get("CASH", 0.0) + released
        return adjusted

    @staticmethod
    def _fail_closed(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "base_allocations": {"CASH": 100.0},
            "regime_adjusted_allocations": {"CASH": 100.0},
            "detected_regime": REGIME_UNKNOWN,
            "allocation_bias": "DEFENSIVE",
            "reasons": [reason],
            "advisory_only": True,
        }

    def _limited_no_allocations(self, regime_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        context = regime_context if isinstance(regime_context, Mapping) else {}
        regime = self._canonical_regime(context.get("detected_regime", context.get("market_regime", REGIME_UNKNOWN)))
        return {
            "status": "LIMITED",
            "base_allocations": {},
            "regime_adjusted_allocations": {},
            "detected_regime": regime,
            "allocation_bias": "NO_PORTFOLIO",
            "reasons": ["No current exposure."],
            "advisory_only": True,
        }
