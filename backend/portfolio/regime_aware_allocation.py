from __future__ import annotations

from typing import Any, Mapping


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
        if not isinstance(base_allocations, Mapping) or not base_allocations:
            return self._fail_closed("base_allocations_unavailable")

        base = self._normalize_allocations(base_allocations)
        if not base:
            return self._fail_closed("base_allocations_invalid")

        context = regime_context if isinstance(regime_context, Mapping) else {}
        regime = str(context.get("detected_regime", context.get("market_regime", "UNKNOWN"))).strip().upper()
        if regime not in {"TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY"}:
            regime = "UNKNOWN"

        drawdown = self._float(context.get("max_drawdown", context.get("drawdown", 0.0)))
        downside_ok = drawdown <= 0.08 and str(context.get("risk_status", "GREEN")).upper() != "RED"
        adjusted = dict(base)
        reasons: list[str] = []

        if regime == "HIGH_VOLATILITY":
            adjusted = self._shift_to_cash(adjusted, 15.0)
            adjusted = self._reduce_high_risk(adjusted, 0.80)
            bias = "DEFENSIVE"
            reasons.append("High volatility increases defensive reserve and reduces high-risk classes.")
        elif regime == "TRENDING" and downside_ok:
            adjusted = self._shift_from_cash(adjusted, 5.0)
            bias = "GROWTH"
            reasons.append("Trending regime with acceptable downside supports selective risk-on allocation.")
        elif regime == "LOW_VOLATILITY":
            bias = "BALANCED"
            reasons.append("Low volatility supports balanced allocation posture.")
        elif regime == "RANGING":
            adjusted = self._shift_to_cash(adjusted, 5.0)
            bias = "BALANCED"
            reasons.append("Ranging regime keeps modest defensive reserve.")
        else:
            adjusted = self._shift_to_cash(adjusted, 10.0)
            bias = "DEFENSIVE"
            reasons.append("Unknown regime remains conservative.")

        adjusted = self._normalize_allocations(adjusted)
        return {
            "status": "OK",
            "base_allocations": base,
            "regime_adjusted_allocations": adjusted,
            "detected_regime": regime,
            "allocation_bias": bias,
            "reasons": reasons,
            "advisory_only": True,
        }

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
    def _normalize_allocations(values: Mapping[str, Any]) -> dict[str, float]:
        rows = []
        for key, value in values.items():
            name = str(key or "").strip().upper()
            if not name:
                continue
            weight = max(0.0, RegimeAwareAllocationEngine._float(value))
            rows.append({"name": name, "weight": weight})
        total = sum(row["weight"] for row in rows)
        if total <= 0.0:
            return {}

        basis_rows = []
        allocated = 0
        for row in sorted(rows, key=lambda item: item["name"]):
            exact = (row["weight"] / total) * 10000.0
            whole = int(exact)
            allocated += whole
            basis_rows.append({"name": row["name"], "basis_points": whole, "remainder": exact - whole})
        remaining = 10000 - allocated
        for row in sorted(basis_rows, key=lambda item: (-item["remainder"], item["name"]))[:remaining]:
            row["basis_points"] += 1
        return {row["name"]: round(row["basis_points"] / 100.0, 2) for row in sorted(basis_rows, key=lambda item: item["name"])}

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _fail_closed(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "base_allocations": {"CASH": 100.0},
            "regime_adjusted_allocations": {"CASH": 100.0},
            "detected_regime": "UNKNOWN",
            "allocation_bias": "DEFENSIVE",
            "reasons": [reason],
            "advisory_only": True,
        }
