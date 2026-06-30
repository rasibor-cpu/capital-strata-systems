from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.portfolio.utils import safe_float


class RuntimeExposureBuilderError(RuntimeError):
    """Fail-closed exception for runtime exposure construction."""


class RuntimeExposureBuilder:
    """Build deterministic exposure views from canonical runtime positions."""

    def build(self, positions: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        if positions is None:
            return self._unavailable("positions_unavailable")
        if isinstance(positions, (str, bytes)) or not isinstance(positions, Iterable):
            return self._unavailable("positions_must_be_iterable")

        try:
            rows = [self._normalize_position(row) for row in positions]
        except RuntimeExposureBuilderError as exc:
            return self._unavailable(str(exc))

        rows = [row for row in rows if row["exposure"] > 0.0]
        if not rows:
            return {
                "status": "LIMITED",
                "portfolio_state": "NO_PORTFOLIO",
                "asset_class_exposure": {},
                "symbol_exposure": {},
                "sector_exposure": {},
                "strategy_exposure": {},
                "directional_exposure": {},
                "concentration_metrics": {
                    "largest_symbol_concentration": 0.0,
                    "largest_asset_class_concentration": 0.0,
                    "largest_strategy_concentration": 0.0,
                },
                "diversification_metrics": {
                    "asset_class_count": 0,
                    "symbol_count": 0,
                    "sector_count": 0,
                    "strategy_count": 0,
                    "diversification_score": 0.0,
                },
                "total_exposure": 0.0,
                "reasons": ["No current exposure."],
                "advisory_only": True,
                "execution_allowed": False,
            }

        total = sum(row["exposure"] for row in rows)
        asset = self._sum_by(rows, "asset_class")
        symbol = self._sum_by(rows, "symbol")
        sector = self._sum_by(rows, "sector")
        strategy = self._sum_by(rows, "strategy_id")
        direction = self._sum_by(rows, "direction")
        concentration = {
            "largest_symbol_concentration": self._largest(symbol, total),
            "largest_asset_class_concentration": self._largest(asset, total),
            "largest_strategy_concentration": self._largest(strategy, total),
        }
        diversification_score = min(100.0, (len(asset) * 18.0) + (len(symbol) * 8.0) + (len(sector) * 4.0))
        portfolio_state = "ACTIVE_PORTFOLIO" if rows else "NO_PORTFOLIO"

        return {
            "status": "OK",
            "portfolio_state": portfolio_state,
            "asset_class_exposure": self._percent_map(asset, total),
            "symbol_exposure": self._percent_map(symbol, total),
            "sector_exposure": self._percent_map(sector, total),
            "strategy_exposure": self._percent_map(strategy, total),
            "directional_exposure": self._percent_map(direction, total),
            "concentration_metrics": concentration,
            "diversification_metrics": {
                "asset_class_count": len(asset),
                "symbol_count": len(symbol),
                "sector_count": len(sector),
                "strategy_count": len(strategy),
                "diversification_score": round(diversification_score, 6),
            },
            "total_exposure": round(total, 8),
            "reasons": [],
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _normalize_position(self, row: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(row, Mapping):
            raise RuntimeExposureBuilderError("position_row_not_mapping")
        symbol = str(row.get("symbol") or row.get("asset") or "").strip().upper()
        if not symbol:
            raise RuntimeExposureBuilderError("position_symbol_missing")
        asset_class = str(row.get("asset_class") or row.get("class") or "UNKNOWN").strip().upper() or "UNKNOWN"
        sector = str(row.get("sector") or asset_class).strip().upper() or "UNKNOWN"
        strategy = str(row.get("strategy_id") or row.get("strategy") or "UNSPECIFIED").strip().upper() or "UNSPECIFIED"
        direction = str(row.get("direction") or row.get("side") or "LONG").strip().upper() or "LONG"
        exposure = self._exposure(row)
        return {
            "symbol": symbol,
            "asset_class": asset_class,
            "sector": sector,
            "strategy_id": strategy,
            "direction": direction,
            "exposure": abs(exposure),
        }

    @staticmethod
    def _exposure(row: Mapping[str, Any]) -> float:
        for key in ("exposure_value", "market_value", "notional_value", "position_value", "current_value", "value"):
            if row.get(key) is not None:
                return safe_float(row.get(key))
        quantity = safe_float(row.get("quantity", row.get("size", 0.0)))
        price = safe_float(row.get("current_price", row.get("entry_price", row.get("price", 1.0))), 1.0)
        return quantity * price

    @staticmethod
    def _sum_by(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
        totals: dict[str, float] = {}
        for row in rows:
            name = str(row[key] or "UNKNOWN").upper()
            totals[name] = totals.get(name, 0.0) + row["exposure"]
        return totals

    @staticmethod
    def _largest(values: Mapping[str, float], total: float) -> float:
        if total <= 0.0 or not values:
            return 0.0
        return round(max(values.values()) / total, 8)

    @staticmethod
    def _percent_map(values: Mapping[str, float], total: float) -> dict[str, float]:
        if total <= 0.0:
            return {}
        return {key: round((values[key] / total) * 100.0, 6) for key in sorted(values.keys())}

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "portfolio_state": "BROKEN_PIPELINE",
            "asset_class_exposure": {},
            "symbol_exposure": {},
            "sector_exposure": {},
            "strategy_exposure": {},
            "directional_exposure": {},
            "concentration_metrics": {},
            "diversification_metrics": {},
            "total_exposure": 0.0,
            "reasons": [reason],
            "advisory_only": True,
            "execution_allowed": False,
        }
