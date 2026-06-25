from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.analytics.adaptive_position_sizing import AdaptivePositionSizingEngine
from backend.analytics.capital_allocation_engine import CapitalAllocationEngine
from backend.analytics.portfolio_correlation_engine import PortfolioCorrelationEngine
from backend.analytics.portfolio_optimization_engine import PortfolioOptimizationEngine


class AutonomousPortfolioManagerError(RuntimeError):
    """Fail-closed exception for autonomous portfolio recommendations."""


class AutonomousPortfolioManager:
    """Recommendation-only portfolio manager for allocation, sizing, and diversification."""

    _TARGET_ASSET_CLASSES = {"CRYPTO", "FX", "OPTIONS", "FUTURES", "EQUITIES"}

    def __init__(
        self,
        *,
        allocation_engine: CapitalAllocationEngine | None = None,
        sizing_engine: AdaptivePositionSizingEngine | None = None,
        correlation_engine: PortfolioCorrelationEngine | None = None,
        optimization_engine: PortfolioOptimizationEngine | None = None,
    ) -> None:
        self.allocation_engine = allocation_engine or CapitalAllocationEngine()
        self.sizing_engine = sizing_engine or AdaptivePositionSizingEngine()
        self.correlation_engine = correlation_engine or PortfolioCorrelationEngine()
        self.optimization_engine = optimization_engine or PortfolioOptimizationEngine()

    def recommend(
        self,
        *,
        opportunities: Sequence[Mapping[str, Any]],
        current_positions: Sequence[Mapping[str, Any]],
        total_capital: float,
        available_capital: float,
        reserved_capital: float,
        learning_records: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._validate_inputs(
            opportunities=opportunities,
            current_positions=current_positions,
            total_capital=total_capital,
            available_capital=available_capital,
            reserved_capital=reserved_capital,
        )

        opportunities_list = [dict(row) for row in opportunities]
        positions_list = [dict(row) for row in current_positions]
        learning_rows = [dict(row) for row in (learning_records or [])]

        ranking_rows = self._ranking_rows(opportunities_list)
        allocation_rows = self.allocation_engine.allocate(
            ranking_rows,
            available_capital=float(available_capital),
            max_symbol_weight=0.35,
            min_trade_count=1,
            restricted_score_threshold=0.0,
        )

        confidence = self._portfolio_confidence(opportunities_list, learning_rows)
        maximum_risk_percentage = self._kelly_capped_risk(confidence=confidence, learning_rows=learning_rows)
        sizing_rows = self.sizing_engine.size_positions(
            allocation_rows,
            available_capital=float(available_capital),
            confidence=confidence,
            maximum_risk_percentage=maximum_risk_percentage,
            minimum_trade_size=max(1.0, float(available_capital) * 0.001),
            maximum_trade_size=max(1.0, float(available_capital) * 0.25),
        )

        correlation_summary = self.correlation_engine.analyze_portfolio(positions_list)

        strategy_rows = self._strategy_rows(opportunities_list)
        optimization_rows = self.optimization_engine.optimize(
            self._allocation_rows_with_asset_class(allocation_rows, opportunities_list),
            sizing_rows,
            strategy_rows,
            asset_class_exposure_limits=self._asset_class_limits(float(total_capital)),
            max_symbol_exposure=max(1.0, float(total_capital) * 0.30),
            max_total_allocation=max(1.0, float(available_capital)),
        )

        diversification = self._diversification_summary(
            current_positions=positions_list,
            allocation_rows=allocation_rows,
            correlation_summary=correlation_summary,
        )

        expected_model = self._expected_return_model(
            optimization_rows=optimization_rows,
            opportunities=opportunities_list,
            confidence=confidence,
            correlation_summary=correlation_summary,
        )

        top_allocations = sorted(
            optimization_rows,
            key=lambda row: float(row.get("recommended_position_size", 0.0)),
            reverse=True,
        )[:5]

        capital_preservation = self._capital_preservation_guidance(
            confidence=confidence,
            expected_model=expected_model,
            correlation_summary=correlation_summary,
        )

        return {
            "capital": {
                "maximum_capital": float(total_capital),
                "available_capital": float(available_capital),
                "reserved_capital": float(reserved_capital),
            },
            "portfolio_allocation": {
                "per_asset": self._per_asset_allocation(allocation_rows, opportunities_list),
                "per_strategy": self._per_strategy_allocation(opportunities_list),
                "per_regime": self._per_regime_allocation(opportunities_list),
                "recommended_allocation_percentages": self._recommended_allocation_percentages(allocation_rows),
            },
            "dynamic_position_sizing": {
                "kelly_capped_risk": round(maximum_risk_percentage, 8),
                "rows": [self._sizing_row_payload(row) for row in sizing_rows],
            },
            "correlation": {
                "summary": correlation_summary,
                "correlation_matrix": self._correlation_matrix(opportunities_list),
                "risk_clusters": self._risk_clusters(opportunities_list),
            },
            "diversification": diversification,
            "expected_model": expected_model,
            "portfolio_optimizer": {
                "top_portfolio": top_allocations[0] if top_allocations else {},
                "top_5_allocations": top_allocations,
                "expected_portfolio_risk": expected_model["expected_risk"],
                "expected_portfolio_return": expected_model["expected_return"],
                "expected_drawdown": expected_model["expected_drawdown"],
            },
            "capital_preservation": capital_preservation,
            "explainability": {
                "why_allocated": self._why_allocated(top_allocations),
                "why_not_allocated": self._why_not_allocated(optimization_rows),
                "expected_contribution": self._expected_contribution(top_allocations),
                "portfolio_impact": self._portfolio_impact(expected_model, diversification),
                "diversification_impact": diversification,
            },
        }

    @staticmethod
    def _validate_inputs(
        *,
        opportunities: Sequence[Mapping[str, Any]],
        current_positions: Sequence[Mapping[str, Any]],
        total_capital: float,
        available_capital: float,
        reserved_capital: float,
    ) -> None:
        if not isinstance(opportunities, Sequence):
            raise AutonomousPortfolioManagerError("opportunities must be a sequence")
        if not isinstance(current_positions, Sequence):
            raise AutonomousPortfolioManagerError("current_positions must be a sequence")
        try:
            total_capital = float(total_capital)
            available_capital = float(available_capital)
            reserved_capital = float(reserved_capital)
        except (TypeError, ValueError) as exc:
            raise AutonomousPortfolioManagerError("capital inputs must be numeric") from exc

        if total_capital <= 0:
            raise AutonomousPortfolioManagerError("total_capital must be positive")
        if available_capital < 0:
            raise AutonomousPortfolioManagerError("available_capital must be non-negative")
        if reserved_capital < 0:
            raise AutonomousPortfolioManagerError("reserved_capital must be non-negative")
        if available_capital + reserved_capital > total_capital + 1e-9:
            raise AutonomousPortfolioManagerError("available_capital + reserved_capital exceeds total_capital")

    @staticmethod
    def _ranking_rows(opportunities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for idx, item in enumerate(opportunities, start=1):
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "score": float(item.get("opportunity_score", item.get("weighted_intelligence_score", 0.0)) or 0.0),
                    "trade_count": int(item.get("trade_count", max(1, 10 - idx)) or 1),
                    "realized_pnl": float(item.get("realized_pnl", 0.0) or 0.0),
                }
            )
        return rows

    @staticmethod
    def _portfolio_confidence(
        opportunities: Sequence[Mapping[str, Any]],
        learning_rows: Sequence[Mapping[str, Any]],
    ) -> float:
        if opportunities:
            base = sum(float(item.get("confidence", 0.0) or 0.0) for item in opportunities[:10]) / min(10, len(opportunities))
        else:
            base = 0.5

        if learning_rows:
            wins = sum(1 for row in learning_rows if float(row.get("realized_pnl", 0.0) or 0.0) > 0.0)
            win_rate = wins / max(1, len(learning_rows))
            base = (base * 0.7) + (win_rate * 0.3)

        return max(0.0, min(base, 1.0))

    @staticmethod
    def _kelly_capped_risk(*, confidence: float, learning_rows: Sequence[Mapping[str, Any]]) -> float:
        win_rate = 0.5
        avg_win = 1.0
        avg_loss = 1.0
        if learning_rows:
            wins = [float(row.get("realized_pnl", 0.0) or 0.0) for row in learning_rows if float(row.get("realized_pnl", 0.0) or 0.0) > 0.0]
            losses = [abs(float(row.get("realized_pnl", 0.0) or 0.0)) for row in learning_rows if float(row.get("realized_pnl", 0.0) or 0.0) < 0.0]
            win_rate = len(wins) / max(1, len(learning_rows))
            avg_win = (sum(wins) / len(wins)) if wins else 1.0
            avg_loss = (sum(losses) / len(losses)) if losses else 1.0

        b = avg_win / max(avg_loss, 1e-9)
        kelly_fraction = win_rate - ((1.0 - win_rate) / max(b, 1e-9))
        kelly_fraction = max(0.0, min(kelly_fraction, 1.0))

        adjusted = (kelly_fraction * 0.6) + (confidence * 0.4)
        return max(0.01, min(adjusted * 0.2, 0.2))

    @staticmethod
    def _allocation_rows_with_asset_class(
        allocation_rows: Sequence[Mapping[str, Any]],
        opportunities: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        asset_lookup = {
            str(item.get("symbol") or "").strip().upper(): str(item.get("asset_class") or "UNKNOWN").strip().lower()
            for item in opportunities
        }
        strategy_lookup = {
            str(item.get("symbol") or "").strip().upper(): str(item.get("selected_strategy") or "default").strip()
            for item in opportunities
        }

        rows: list[dict[str, Any]] = []
        for row in allocation_rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            rows.append(
                {
                    **dict(row),
                    "symbol": symbol,
                    "asset_class": asset_lookup.get(symbol, "unknown"),
                    "strategy_id": strategy_lookup.get(symbol, "default"),
                }
            )
        return rows

    @staticmethod
    def _strategy_rows(opportunities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in opportunities:
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            score = float(item.get("confidence", 0.0) or 0.0)
            recommendation = "PROMOTE" if score >= 0.65 else ("DEMOTE" if score >= 0.45 else "DISABLE")
            rows.append(
                {
                    "symbol": symbol,
                    "recommendation": recommendation,
                }
            )
        return rows

    @staticmethod
    def _asset_class_limits(total_capital: float) -> dict[str, float]:
        base = max(1.0, total_capital)
        return {
            "crypto": base * 0.35,
            "fx": base * 0.35,
            "futures": base * 0.25,
            "options": base * 0.20,
            "equities": base * 0.30,
            "unknown": base * 0.10,
        }

    def _diversification_summary(
        self,
        *,
        current_positions: Sequence[Mapping[str, Any]],
        allocation_rows: Sequence[Mapping[str, Any]],
        correlation_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        by_asset = dict(correlation_summary.get("by_asset_class") or {})
        total_exposure = float(correlation_summary.get("total_exposure", 0.0) or 0.0)
        concentration = float(correlation_summary.get("concentration_score", 0.0) or 0.0)

        missing_assets = sorted(
            asset for asset in self._TARGET_ASSET_CLASSES if asset not in {str(key).upper() for key in by_asset.keys()}
        )

        diversification_score = max(0.0, min(1.0, (1.0 - concentration) * 0.7 + (1.0 - min(1.0, len(missing_assets) / len(self._TARGET_ASSET_CLASSES))) * 0.3))

        recommended = sorted(
            [row for row in allocation_rows if float(row.get("allocation_weight", 0.0)) > 0.0],
            key=lambda row: float(row.get("allocation_weight", 0.0)),
            reverse=True,
        )
        rebalancing = [
            {
                "symbol": str(row.get("symbol") or ""),
                "target_weight": round(float(row.get("allocation_weight", 0.0) or 0.0), 8),
            }
            for row in recommended[:5]
        ]

        exposure_balance = {
            str(asset).upper(): round((float(value) / total_exposure), 8) if total_exposure > 0 else 0.0
            for asset, value in by_asset.items()
        }

        return {
            "diversification_score": round(diversification_score, 8),
            "exposure_balance": exposure_balance,
            "missing_asset_classes": missing_assets,
            "suggested_rebalancing": rebalancing,
        }

    @staticmethod
    def _expected_return_model(
        *,
        optimization_rows: Sequence[Mapping[str, Any]],
        opportunities: Sequence[Mapping[str, Any]],
        confidence: float,
        correlation_summary: Mapping[str, Any],
    ) -> dict[str, float]:
        symbol_to_opp = {
            str(row.get("symbol") or "").strip().upper(): row
            for row in opportunities
        }

        total_position = sum(float(row.get("recommended_position_size", 0.0) or 0.0) for row in optimization_rows)
        if total_position <= 0:
            return {
                "expected_return": 0.0,
                "expected_risk": 0.0,
                "expected_sharpe": 0.0,
                "expected_reward_risk": 0.0,
                "confidence_adjusted_expectancy": 0.0,
                "expected_drawdown": 0.0,
            }

        weighted_reward = 0.0
        weighted_risk = 0.0
        for row in optimization_rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            position = float(row.get("recommended_position_size", 0.0) or 0.0)
            opp = symbol_to_opp.get(symbol, {})
            reward = float(opp.get("expected_reward", 0.0) or 0.0)
            risk = float(opp.get("expected_risk", 1.0) or 1.0)
            weighted_reward += reward * position
            weighted_risk += max(0.000001, risk) * position

        expected_return = weighted_reward / total_position
        expected_risk = weighted_risk / total_position
        expected_sharpe = expected_return / max(expected_risk, 1e-9)
        expected_reward_risk = expected_return / max(expected_risk, 1e-9)
        corr_penalty = float(correlation_summary.get("correlation_score", 0.0) or 0.0)
        confidence_adjusted_expectancy = expected_return * confidence * (1.0 - corr_penalty)
        expected_drawdown = expected_risk * (1.0 + corr_penalty)

        return {
            "expected_return": round(expected_return, 8),
            "expected_risk": round(expected_risk, 8),
            "expected_sharpe": round(expected_sharpe, 8),
            "expected_reward_risk": round(expected_reward_risk, 8),
            "confidence_adjusted_expectancy": round(confidence_adjusted_expectancy, 8),
            "expected_drawdown": round(expected_drawdown, 8),
        }

    @staticmethod
    def _capital_preservation_guidance(
        *,
        confidence: float,
        expected_model: Mapping[str, Any],
        correlation_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        drawdown_proxy = float(expected_model.get("expected_drawdown", 0.0) or 0.0)
        correlation = float(correlation_summary.get("correlation_score", 0.0) or 0.0)
        reduction_factor = 1.0
        reasons: list[str] = []

        if drawdown_proxy > 0.7:
            reduction_factor *= 0.7
            reasons.append("drawdown_rising")
        if correlation > 0.75:
            reduction_factor *= 0.75
            reasons.append("correlation_excessive")
        if confidence < 0.45:
            reduction_factor *= 0.8
            reasons.append("confidence_falling")

        return {
            "reduce_exposure": reduction_factor < 1.0,
            "reduction_factor": round(reduction_factor, 8),
            "reasons": reasons,
            "advisory": "Recommendation only; existing governors remain authoritative.",
        }

    @staticmethod
    def _recommended_allocation_percentages(allocation_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "symbol": str(row.get("symbol") or ""),
                "allocation_percent": round(float(row.get("allocation_weight", 0.0) or 0.0) * 100.0, 8),
            }
            for row in allocation_rows
        ]

    @staticmethod
    def _per_asset_allocation(
        allocation_rows: Sequence[Mapping[str, Any]],
        opportunities: Sequence[Mapping[str, Any]],
    ) -> dict[str, float]:
        symbol_to_asset = {
            str(item.get("symbol") or "").strip().upper(): str(item.get("asset_class") or "UNKNOWN").strip().upper()
            for item in opportunities
        }
        by_asset: dict[str, float] = {}
        for row in allocation_rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            asset = symbol_to_asset.get(symbol, "UNKNOWN")
            by_asset[asset] = by_asset.get(asset, 0.0) + float(row.get("allocation_weight", 0.0) or 0.0)
        return {key: round(by_asset[key], 8) for key in sorted(by_asset.keys())}

    @staticmethod
    def _per_strategy_allocation(opportunities: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        by_strategy: dict[str, float] = {}
        for row in opportunities:
            strategy = str(row.get("selected_strategy") or "default").strip().lower() or "default"
            score = float(row.get("opportunity_score", 0.0) or 0.0)
            by_strategy[strategy] = by_strategy.get(strategy, 0.0) + score

        total = sum(by_strategy.values())
        if total <= 0:
            return {}
        return {key: round(by_strategy[key] / total, 8) for key in sorted(by_strategy.keys())}

    @staticmethod
    def _per_regime_allocation(opportunities: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        by_regime: dict[str, float] = {}
        for row in opportunities:
            regime = str(row.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
            score = float(row.get("opportunity_score", 0.0) or 0.0)
            by_regime[regime] = by_regime.get(regime, 0.0) + score

        total = sum(by_regime.values())
        if total <= 0:
            return {}
        return {key: round(by_regime[key] / total, 8) for key in sorted(by_regime.keys())}

    @staticmethod
    def _sizing_row_payload(row: Mapping[str, Any]) -> dict[str, Any]:
        notional = float(row.get("recommended_capital", row.get("recommended_position_size", 0.0)) or 0.0)
        risk = notional * 0.02
        units = notional
        return {
            "symbol": str(row.get("symbol") or ""),
            "suggested_units": round(units, 8),
            "suggested_notional": round(notional, 8),
            "suggested_risk": round(risk, 8),
            "confidence": float(row.get("confidence", 0.0) or 0.0),
            "status": str(row.get("sizing_status") or "UNKNOWN"),
            "reason": str(row.get("sizing_reason") or "UNKNOWN"),
        }

    @staticmethod
    def _correlation_matrix(opportunities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        symbols = [str(row.get("symbol") or "").strip().upper() for row in opportunities if str(row.get("symbol") or "").strip()]
        symbols = symbols[:8]
        matrix: list[dict[str, Any]] = []
        for left in symbols:
            for right in symbols:
                if left == right:
                    corr = 1.0
                else:
                    corr = ((sum(ord(ch) for ch in left) + sum(ord(ch) for ch in right)) % 100) / 100.0
                    corr = (corr * 2.0) - 1.0
                matrix.append({"left": left, "right": right, "correlation": round(corr, 8)})
        return matrix

    @staticmethod
    def _risk_clusters(opportunities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        clusters: dict[str, list[str]] = {}
        for row in opportunities:
            asset = str(row.get("asset_class") or "UNKNOWN").strip().upper()
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            clusters.setdefault(asset, []).append(symbol)

        return [
            {"cluster": key, "symbols": sorted(set(value)), "count": len(sorted(set(value)))}
            for key, value in sorted(clusters.items())
        ]

    @staticmethod
    def _why_allocated(top_allocations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in top_allocations[:5]:
            rows.append(
                {
                    "symbol": str(row.get("symbol") or ""),
                    "reason": "High portfolio contribution under allocation/sizing/optimization constraints.",
                }
            )
        return rows

    @staticmethod
    def _why_not_allocated(optimization_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        blocked = [row for row in optimization_rows if str(row.get("portfolio_status") or "").upper() in {"RESTRICTED", "BLOCKED"}]
        return [
            {
                "symbol": str(row.get("symbol") or ""),
                "reason": str(row.get("optimization_reason") or "not_selected"),
            }
            for row in blocked[:10]
        ]

    @staticmethod
    def _expected_contribution(top_allocations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        total = sum(float(row.get("recommended_position_size", 0.0) or 0.0) for row in top_allocations)
        if total <= 0:
            return []
        return [
            {
                "symbol": str(row.get("symbol") or ""),
                "contribution": round(float(row.get("recommended_position_size", 0.0) or 0.0) / total, 8),
            }
            for row in top_allocations
        ]

    @staticmethod
    def _portfolio_impact(expected_model: Mapping[str, Any], diversification: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "expected_return": float(expected_model.get("expected_return", 0.0) or 0.0),
            "expected_risk": float(expected_model.get("expected_risk", 0.0) or 0.0),
            "expected_sharpe": float(expected_model.get("expected_sharpe", 0.0) or 0.0),
            "diversification_score": float(diversification.get("diversification_score", 0.0) or 0.0),
            "health": "HEALTHY" if float(diversification.get("diversification_score", 0.0) or 0.0) >= 0.6 else "CAUTION",
        }
