from __future__ import annotations

from typing import Any, Dict


class EdgeEngine:
    """
    CSS Edge Engine

    Purpose
    -------
    Produces a simple net edge estimate in basis points using:
    - expected opportunity strength
    - pressure
    - acceleration
    - momentum
    - VWAP dislocation
    minus estimated transaction cost

    Notes
    -----
    - No self-imports
    - No circular dependencies
    - Safe defaults for incomplete rows
    - Backward-compatible with dashboard callers that pass a single row dict
    """

    def __init__(
        self,
        pressure_weight: float = 12.0,
        accel_weight: float = 8.0,
        momentum_weight: float = 10.0,
        vwap_dev_weight: float = 15000.0,
        base_score_weight: float = 10.0,
        cost_floor_bps: float = 5.0,
    ) -> None:
        self.pressure_weight = float(pressure_weight)
        self.accel_weight = float(accel_weight)
        self.momentum_weight = float(momentum_weight)
        self.vwap_dev_weight = float(vwap_dev_weight)
        self.base_score_weight = float(base_score_weight)
        self.cost_floor_bps = float(cost_floor_bps)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _extract_cost_bps(self, row: Dict[str, Any]) -> float:
        spread = self._safe_float(row.get("spread"), 0.0)
        spread_bps = self._safe_float(row.get("spread_bps"), 0.0)
        estimated_cost_bps = self._safe_float(row.get("estimated_cost_bps"), 0.0)

        candidates = [v for v in (estimated_cost_bps, spread_bps, spread) if v > 0]

        if candidates:
            return max(candidates[0], self.cost_floor_bps)

        return self.cost_floor_bps

    def compute_edge(self, row: Dict[str, Any]) -> float:
        if not isinstance(row, dict):
            return 0.0

        base_score = self._safe_float(
            row.get("score", row.get("trade_score", row.get("decision_score", 0.0))),
            0.0,
        )
        pressure = self._safe_float(
            row.get("pressure_score", row.get("pressure", row.get("opportunity_pressure", 0.0))),
            0.0,
        )
        accel = self._safe_float(
            row.get("pressure_acceleration", row.get("accel", row.get("acceleration_score", 0.0))),
            0.0,
        )
        momentum = self._safe_float(row.get("momentum", 0.0), 0.0)

        price = self._safe_float(row.get("price"), 0.0)
        vwap = self._safe_float(row.get("vwap"), 0.0)

        vwap_dev_abs = self._safe_float(row.get("vwap_dev_abs"), 0.0)
        if vwap_dev_abs <= 0 and price > 0 and vwap > 0:
            vwap_dev_abs = abs(price - vwap) / vwap

        gross_edge_bps = (
            (base_score * self.base_score_weight)
            + (pressure * self.pressure_weight)
            + (accel * self.accel_weight)
            + (momentum * self.momentum_weight)
            + (vwap_dev_abs * self.vwap_dev_weight)
        )

        cost_bps = self._extract_cost_bps(row)
        net_edge_bps = gross_edge_bps - cost_bps

        return round(net_edge_bps, 4)