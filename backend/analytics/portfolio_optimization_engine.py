from __future__ import annotations

from typing import Any


class PortfolioOptimizationError(RuntimeError):
    """Explicit fail-closed exception for portfolio optimization failures."""


class PortfolioOptimizationEngine:
    """Recommend backend-only portfolio allocation adjustments without executing trades."""

    def optimize(
        self,
        allocation_rows: list[dict[str, Any]],
        sizing_rows: list[dict[str, Any]],
        strategy_rows: list[dict[str, Any]],
        *,
        asset_class_exposure_limits: dict[str, float],
        max_symbol_exposure: float,
        max_total_allocation: float,
    ) -> list[dict[str, Any]]:
        self._validate_inputs(
            allocation_rows=allocation_rows,
            sizing_rows=sizing_rows,
            strategy_rows=strategy_rows,
            asset_class_exposure_limits=asset_class_exposure_limits,
            max_symbol_exposure=max_symbol_exposure,
            max_total_allocation=max_total_allocation,
        )

        if not allocation_rows or not sizing_rows:
            return []

        by_symbol = {str(row.get("symbol", "")).strip(): row for row in allocation_rows if str(row.get("symbol", "")).strip()}
        sizing_by_symbol = {
            str(row.get("symbol", "")).strip(): row
            for row in sizing_rows
            if str(row.get("symbol", "")).strip()
        }
        strategy_by_symbol = {}
        for row in strategy_rows:
            symbol = str(row.get("symbol", "")).strip()
            if symbol:
                strategy_by_symbol[symbol] = row

        optimized: list[dict[str, Any]] = []
        total_allocation = 0.0
        exposure_by_asset_class: dict[str, float] = {}
        exposure_by_symbol: dict[str, float] = {}

        for symbol, allocation_row in by_symbol.items():
            symbol_name = str(allocation_row.get("symbol", "")).strip()
            asset_class = str(allocation_row.get("asset_class", "unknown")).strip() or "unknown"
            strategy_id = str(allocation_row.get("strategy_id", "unknown")).strip() or "unknown"
            allocation_weight = float(allocation_row.get("allocation_weight", 0.0))
            sizing_row = sizing_by_symbol.get(symbol_name, {})
            strategy_row = strategy_by_symbol.get(symbol_name, {})
            recommended_position_size = float(sizing_row.get("recommended_position_size", 0.0))
            strategy_action = str(strategy_row.get("recommendation", "HOLD"))
            status = "APPROVED"
            reason = "allocation_and_sizing_approved"

            if allocation_weight <= 0.0:
                status = "RESTRICTED"
                reason = "allocation_weight_zero"
                recommended_position_size = 0.0
            elif strategy_action in {"DEMOTE", "DISABLE"}:
                status = "REDUCED" if strategy_action == "DEMOTE" else "BLOCKED"
                reason = "strategy_recommendation"
                recommended_position_size = 0.0 if strategy_action == "DISABLE" else recommended_position_size * 0.5
            elif symbol_name in {"", "UNKNOWN"}:
                status = "BLOCKED"
                reason = "missing_symbol"
                recommended_position_size = 0.0

            if status in {"APPROVED", "REDUCED"}:
                if recommended_position_size > max_symbol_exposure:
                    status = "REDUCED"
                    recommended_position_size = max_symbol_exposure
                    reason = "symbol_exposure_cap"
                if total_allocation + recommended_position_size > max_total_allocation:
                    status = "REDUCED"
                    recommended_position_size = max(0.0, max_total_allocation - total_allocation)
                    reason = "total_allocation_cap"

            if status == "APPROVED" and allocation_weight > 0.0:
                current_asset_exposure = exposure_by_asset_class.get(asset_class, 0.0)
                asset_limit = float(asset_class_exposure_limits.get(asset_class, 1.0))
                if current_asset_exposure + recommended_position_size > asset_limit:
                    status = "REDUCED"
                    recommended_position_size = max(0.0, asset_limit - current_asset_exposure)
                    reason = "asset_class_exposure_cap"

            if status == "RESTRICTED" or status == "BLOCKED":
                recommended_position_size = 0.0

            exposure_by_asset_class[asset_class] = exposure_by_asset_class.get(asset_class, 0.0) + recommended_position_size
            exposure_by_symbol[symbol_name] = exposure_by_symbol.get(symbol_name, 0.0) + recommended_position_size
            total_allocation += recommended_position_size

            optimized.append(
                {
                    "symbol": symbol_name,
                    "asset_class": asset_class,
                    "strategy_id": strategy_id,
                    "allocation_weight": allocation_weight,
                    "recommended_position_size": recommended_position_size,
                    "strategy_action": strategy_action,
                    "portfolio_status": status,
                    "optimization_reason": reason,
                }
            )

        return optimized

    @staticmethod
    def _validate_inputs(
        *,
        allocation_rows: list[dict[str, Any]],
        sizing_rows: list[dict[str, Any]],
        strategy_rows: list[dict[str, Any]],
        asset_class_exposure_limits: dict[str, float],
        max_symbol_exposure: float,
        max_total_allocation: float,
    ) -> None:
        try:
            max_symbol_exposure = float(max_symbol_exposure)
            max_total_allocation = float(max_total_allocation)
        except (TypeError, ValueError) as exc:
            raise PortfolioOptimizationError("Exposure limits must be numeric") from exc

        if not isinstance(allocation_rows, list) or not isinstance(sizing_rows, list) or not isinstance(strategy_rows, list):
            raise PortfolioOptimizationError("Inputs must be lists")
        if not isinstance(asset_class_exposure_limits, dict):
            raise PortfolioOptimizationError("asset_class_exposure_limits must be a dictionary")
        if max_symbol_exposure <= 0.0:
            raise PortfolioOptimizationError("max_symbol_exposure must be positive")
        if max_total_allocation <= 0.0:
            raise PortfolioOptimizationError("max_total_allocation must be positive")
        for asset_class, limit in asset_class_exposure_limits.items():
            try:
                value = float(limit)
            except (TypeError, ValueError) as exc:
                raise PortfolioOptimizationError("Asset class limits must be numeric") from exc
            if value <= 0.0:
                raise PortfolioOptimizationError("Asset class exposure limits must be positive")
