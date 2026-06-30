from __future__ import annotations

from typing import Any, Iterable, Mapping


class PortfolioIntelligenceEngineError(RuntimeError):
    """Fail-closed exception for portfolio intelligence analysis."""


class PortfolioIntelligenceEngine:
    """
    Deterministic, advisory-only portfolio intelligence analysis.

    The engine reads portfolio evidence and produces scores, findings, and
    explanations. It does not execute trades or alter risk gates.
    """

    def analyze(
        self,
        positions: Iterable[Mapping[str, Any]] | None,
        performance_metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if positions is None:
            return self._unavailable("positions_unavailable")
        if not isinstance(positions, Iterable):
            return self._unavailable("positions_must_be_iterable")

        try:
            records = [self._normalize_position(row) for row in positions]
        except PortfolioIntelligenceEngineError as exc:
            return self._unavailable(str(exc))

        records = [row for row in records if row["exposure"] > 0.0]
        if not records:
            return self._limited_no_exposure()

        metrics = dict(performance_metrics or {})
        total_exposure = sum(row["exposure"] for row in records)
        by_asset_class: dict[str, float] = {}
        by_symbol: dict[str, float] = {}
        for row in records:
            by_asset_class[row["asset_class"]] = by_asset_class.get(row["asset_class"], 0.0) + row["exposure"]
            by_symbol[row["symbol"]] = by_symbol.get(row["symbol"], 0.0) + row["exposure"]

        concentration = max(by_symbol.values()) / total_exposure if total_exposure else 0.0
        asset_concentration = max(by_asset_class.values()) / total_exposure if total_exposure else 0.0
        correlation = self._float(metrics.get("correlation_score", metrics.get("average_correlation", 0.0)))
        drawdown = self._float(metrics.get("max_drawdown", metrics.get("drawdown", 0.0)))
        sortino = self._float(metrics.get("sortino", metrics.get("sortino_ratio", 0.0)))
        capital_efficiency = self._float(metrics.get("capital_efficiency", 0.0))

        penalty_components = {
            "drawdown": self._drawdown_penalty(drawdown),
            "sortino": self._sortino_penalty(sortino),
            "capital_efficiency": self._capital_efficiency_penalty(capital_efficiency),
            "concentration": self._concentration_penalty(max(concentration, asset_concentration)),
            "correlation": self._correlation_penalty(correlation),
        }
        total_penalty = min(100.0, sum(penalty_components.values()))
        intelligence_score = round(max(0.0, 100.0 - total_penalty), 6)

        if intelligence_score >= 80.0:
            status = "HEALTHY"
        elif intelligence_score >= 60.0:
            status = "WATCH"
        else:
            status = "DEFENSIVE"

        findings = self._findings(penalty_components)
        recommendation = "MAINTAIN" if status == "HEALTHY" else ("REBALANCE" if status == "WATCH" else "REDUCE_RISK")

        return {
            "status": "OK",
            "advisory_only": True,
            "execution_allowed": False,
            "portfolio_status": status,
            "intelligence_score": intelligence_score,
            "recommendation": recommendation,
            "metrics": {
                "total_exposure": round(total_exposure, 8),
                "asset_class_count": len(by_asset_class),
                "symbol_count": len(by_symbol),
                "largest_symbol_concentration": round(concentration, 8),
                "largest_asset_class_concentration": round(asset_concentration, 8),
                "correlation_score": round(max(0.0, min(correlation, 1.0)), 8),
                "max_drawdown": round(max(0.0, drawdown), 8),
                "sortino": round(sortino, 8),
                "capital_efficiency": round(capital_efficiency, 8),
            },
            "penalties": {key: round(value, 6) for key, value in sorted(penalty_components.items())},
            "explainability": findings,
            "by_asset_class": self._percent_map(by_asset_class, total_exposure),
            "by_symbol": self._percent_map(by_symbol, total_exposure),
        }

    def _normalize_position(self, row: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(row, Mapping):
            raise PortfolioIntelligenceEngineError("position_row_not_mapping")
        symbol = str(row.get("symbol") or row.get("asset") or "").strip().upper()
        asset_class = str(row.get("asset_class") or "UNKNOWN").strip().upper() or "UNKNOWN"
        if not symbol:
            raise PortfolioIntelligenceEngineError("position_symbol_missing")
        exposure = self._extract_exposure(row)
        return {
            "symbol": symbol,
            "asset_class": asset_class,
            "exposure": max(0.0, abs(exposure)),
        }

    def _extract_exposure(self, row: Mapping[str, Any]) -> float:
        for field in ("exposure_value", "market_value", "notional_value", "position_value", "current_value", "value"):
            if row.get(field) is not None:
                return self._float(row.get(field))
        quantity = self._float(row.get("quantity", row.get("size", 0.0)))
        price = self._float(row.get("current_price", row.get("entry_price", row.get("price", 1.0))))
        return quantity * price

    @staticmethod
    def _drawdown_penalty(drawdown: float) -> float:
        if drawdown <= 0.05:
            return 0.0
        return max(0.0, min(25.0, (drawdown - 0.05) * 125.0))

    @staticmethod
    def _sortino_penalty(sortino: float) -> float:
        if sortino >= 1.5:
            return 0.0
        return min(20.0, (1.5 - sortino) * 10.0)

    @staticmethod
    def _capital_efficiency_penalty(capital_efficiency: float) -> float:
        if capital_efficiency >= 0.70:
            return 0.0
        return min(20.0, (0.70 - capital_efficiency) * 25.0)

    @staticmethod
    def _concentration_penalty(concentration: float) -> float:
        if concentration <= 0.45:
            return 0.0
        return min(20.0, (concentration - 0.45) * 40.0)

    @staticmethod
    def _correlation_penalty(correlation: float) -> float:
        if correlation <= 0.45:
            return 0.0
        return min(15.0, (correlation - 0.45) * 30.0)

    @staticmethod
    def _findings(penalties: Mapping[str, float]) -> list[str]:
        labels = {
            "drawdown": "High drawdown is reducing portfolio readiness.",
            "sortino": "Weak Sortino ratio is reducing risk-adjusted quality.",
            "capital_efficiency": "Poor capital efficiency is reducing allocation quality.",
            "concentration": "High concentration is increasing portfolio fragility.",
            "correlation": "Excessive correlation is reducing diversification.",
        }
        findings = [labels[key] for key in sorted(penalties.keys()) if penalties[key] > 0.0]
        return findings or ["Portfolio evidence supports current allocation posture."]

    @staticmethod
    def _percent_map(values: Mapping[str, float], total: float) -> dict[str, float]:
        if total <= 0:
            return {}
        return {key: round((values[key] / total) * 100.0, 6) for key in sorted(values.keys())}

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _unavailable(message: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "advisory_only": True,
            "execution_allowed": False,
            "portfolio_status": "UNKNOWN",
            "intelligence_score": 0.0,
            "recommendation": "NO_ACTION",
            "metrics": {},
            "penalties": {},
            "explainability": [message],
            "by_asset_class": {},
            "by_symbol": {},
        }

    @staticmethod
    def _limited_no_exposure() -> dict[str, Any]:
        return {
            "status": "LIMITED",
            "advisory_only": True,
            "execution_allowed": False,
            "portfolio_status": "NO_PORTFOLIO",
            "intelligence_score": 50.0,
            "recommendation": "HOLD_CURRENT",
            "metrics": {
                "total_exposure": 0.0,
                "asset_class_count": 0,
                "symbol_count": 0,
                "largest_symbol_concentration": 0.0,
                "largest_asset_class_concentration": 0.0,
                "correlation_score": 0.0,
                "max_drawdown": 0.0,
                "sortino": 0.0,
                "capital_efficiency": 0.0,
            },
            "penalties": {},
            "explainability": ["No current exposure."],
            "by_asset_class": {},
            "by_symbol": {},
        }
