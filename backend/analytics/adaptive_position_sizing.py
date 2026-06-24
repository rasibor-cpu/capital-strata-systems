from __future__ import annotations

from typing import Any


class AdaptivePositionSizingError(RuntimeError):
    """Explicit fail-closed exception for adaptive position sizing failures."""


class AdaptivePositionSizingEngine:
    """Convert approved allocations into backend-only position sizing recommendations."""

    def size_positions(
        self,
        allocations: list[dict[str, Any]],
        *,
        available_capital: float,
        confidence: float,
        maximum_risk_percentage: float,
        minimum_trade_size: float,
        maximum_trade_size: float,
    ) -> list[dict[str, Any]]:
        self._validate_inputs(
            allocations=allocations,
            available_capital=available_capital,
            confidence=confidence,
            maximum_risk_percentage=maximum_risk_percentage,
            minimum_trade_size=minimum_trade_size,
            maximum_trade_size=maximum_trade_size,
        )

        sized_rows: list[dict[str, Any]] = []
        for allocation in allocations:
            symbol = str(allocation.get("symbol", "")).strip()
            if not symbol:
                raise AdaptivePositionSizingError("Allocation row is missing a symbol")
            allocation_weight = float(allocation.get("allocation_weight", 0.0))
            allocation_amount = float(allocation.get("allocation_amount", 0.0))
            if allocation_weight <= 0.0 or allocation_amount <= 0.0:
                sized_rows.append(
                    {
                        "symbol": symbol,
                        "recommended_position_size": 0.0,
                        "recommended_capital": 0.0,
                        "confidence": float(confidence),
                        "sizing_reason": "allocation_not_approved",
                        "sizing_status": "REJECTED",
                    }
                )
                continue

            risk_budget = min(
                allocation_amount * maximum_risk_percentage,
                available_capital * maximum_risk_percentage,
                maximum_trade_size,
            )
            adjusted_capital = risk_budget
            if float(confidence) < 0.75:
                adjusted_capital *= float(confidence)
            adjusted_capital = max(minimum_trade_size, adjusted_capital)
            adjusted_capital = min(adjusted_capital, maximum_trade_size)

            sized_rows.append(
                {
                    "symbol": symbol,
                    "recommended_position_size": adjusted_capital,
                    "recommended_capital": adjusted_capital,
                    "confidence": float(confidence),
                    "sizing_reason": "confidence_and_risk_adjusted",
                    "sizing_status": "APPROVED",
                }
            )

        return sized_rows

    @staticmethod
    def _validate_inputs(
        *,
        allocations: list[dict[str, Any]],
        available_capital: float,
        confidence: float,
        maximum_risk_percentage: float,
        minimum_trade_size: float,
        maximum_trade_size: float,
    ) -> None:
        try:
            available_capital = float(available_capital)
            confidence = float(confidence)
            maximum_risk_percentage = float(maximum_risk_percentage)
            minimum_trade_size = float(minimum_trade_size)
            maximum_trade_size = float(maximum_trade_size)
        except (TypeError, ValueError) as exc:
            raise AdaptivePositionSizingError("Adaptive position sizing inputs must be numeric") from exc

        if available_capital <= 0.0:
            raise AdaptivePositionSizingError("available_capital must be positive")
        if not 0.0 <= confidence <= 1.0:
            raise AdaptivePositionSizingError("confidence must be between 0 and 1")
        if not 0.0 < maximum_risk_percentage <= 1.0:
            raise AdaptivePositionSizingError("maximum_risk_percentage must be between 0 and 1")
        if minimum_trade_size <= 0.0:
            raise AdaptivePositionSizingError("minimum_trade_size must be positive")
        if maximum_trade_size <= 0.0 or maximum_trade_size < minimum_trade_size:
            raise AdaptivePositionSizingError("maximum_trade_size must be positive and >= minimum_trade_size")
        if not isinstance(allocations, list):
            raise AdaptivePositionSizingError("allocations must be a list")
