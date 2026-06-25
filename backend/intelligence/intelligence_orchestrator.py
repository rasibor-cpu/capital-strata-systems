from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend.analytics.adaptive_exit_engine import AdaptiveExitEngine
from backend.analytics.adaptive_position_sizing import AdaptivePositionSizingEngine
from backend.analytics.capital_allocation_engine import CapitalAllocationEngine
from backend.analytics.concentration_guard import ConcentrationGuard
from backend.analytics.market_regime_engine import MarketRegimeEngine
from backend.analytics.portfolio_correlation_engine import PortfolioCorrelationEngine


class IntelligenceDecisionError(RuntimeError):
    """Fail-closed exception for intelligence orchestration failures."""


@dataclass(frozen=True)
class IntelligenceDecision:
    timestamp: str
    asset_class: str
    symbol: str
    market_regime: str
    selected_strategy: str
    signal_strength: float
    confidence: float
    strategy_score: float
    allocation: dict[str, Any]
    position_size: dict[str, Any]
    portfolio_risk: float
    concentration_score: float
    entry_decision: str
    exit_plan: dict[str, Any]
    expected_reward: float
    expected_risk: float
    approval_reason: str
    rejection_reason: str
    execution_status: str
    learning_context: dict[str, Any]
    overall_confidence: float
    decision: str
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _NullStrategyIntelligenceEngine:
    def rank_strategies_by_context(self, **_: Any) -> list[dict[str, Any]]:
        return []

    def best_strategy_for_symbol(self, _: str) -> dict[str, Any] | None:
        return None

    def best_strategy_for_regime(self, _: str) -> dict[str, Any] | None:
        return None

    def strategy_confidence(self, *_: Any, **__: Any) -> float:
        return 0.0

    def strategy_memory_summary(self) -> dict[str, Any]:
        return {}


class IntelligenceOrchestrator:
    """Recommendation-only intelligence orchestrator with fail-closed behavior."""

    _DEFAULT = object()
    _ALLOWED_DECISIONS = {"ALLOW", "REDUCE_SIZE", "DEFER", "BLOCK"}

    def __init__(
        self,
        *,
        market_regime_engine: Any = _DEFAULT,
        strategy_intelligence_engine: Any = _DEFAULT,
        capital_allocation_engine: Any = _DEFAULT,
        adaptive_position_sizing_engine: Any = _DEFAULT,
        portfolio_correlation_engine: Any = _DEFAULT,
        concentration_guard: Any = _DEFAULT,
        adaptive_exit_engine: Any = _DEFAULT,
    ) -> None:
        self.market_regime_engine = self._resolve_engine(market_regime_engine, MarketRegimeEngine)
        self.strategy_intelligence_engine = self._resolve_strategy_engine(strategy_intelligence_engine)
        self.capital_allocation_engine = self._resolve_engine(capital_allocation_engine, CapitalAllocationEngine)
        self.adaptive_position_sizing_engine = self._resolve_engine(
            adaptive_position_sizing_engine,
            AdaptivePositionSizingEngine,
        )
        self.portfolio_correlation_engine = self._resolve_engine(
            portfolio_correlation_engine,
            PortfolioCorrelationEngine,
        )
        self.concentration_guard = self._resolve_engine(concentration_guard, ConcentrationGuard)
        self.adaptive_exit_engine = self._resolve_engine(adaptive_exit_engine, AdaptiveExitEngine)

    def decide(self, trade_candidate: Mapping[str, Any]) -> IntelligenceDecision:
        candidate = self._normalize_candidate(trade_candidate)
        self._validate_engines()

        try:
            market_features = self.market_regime_engine.analyze_market(candidate["market_candles"])
            market_regime = self._normalize_regime(market_features)
            market_confidence = self._safe_float(market_features.get("confidence"), 0.0)
            volatility = self._safe_float(market_features.get("volatility"), 0.0)
            trend_strength = self._safe_float(market_features.get("trend_strength"), 0.0)

            strategy_score, strategy_details = self._resolve_strategy_recommendation(candidate, market_regime)

            available_capital = self._resolve_available_capital(
                candidate["portfolio_snapshot"],
                candidate["current_price"],
            )
            allocation_rows = self.capital_allocation_engine.allocate(
                [
                    {
                        "symbol": candidate["symbol"],
                        "score": strategy_score,
                        "trade_count": 1,
                        "realized_pnl": 0.0,
                    }
                ],
                available_capital=available_capital,
                max_symbol_weight=0.35,
                min_trade_count=1,
                restricted_score_threshold=0.0,
            )
            allocation = allocation_rows[0] if allocation_rows else self._empty_allocation(candidate["symbol"])
            allocation_weight = self._safe_float(allocation.get("allocation_weight"), 0.0)

            correlation_summary = self.portfolio_correlation_engine.analyze_portfolio(candidate["portfolio_positions"])
            concentration_summary = self.concentration_guard.evaluate(candidate["portfolio_positions"])
            portfolio_risk = self._safe_float(concentration_summary.get("risk_score"), 0.0)
            concentration_score = self._safe_float(
                concentration_summary.get("concentration_score"),
                self._safe_float(correlation_summary.get("concentration_score"), 0.0),
            )

            sizing_rows = self.adaptive_position_sizing_engine.size_positions(
                [allocation],
                available_capital=available_capital,
                confidence=max(0.0, min(1.0, strategy_score)),
                maximum_risk_percentage=self._resolve_risk_budget(portfolio_risk, concentration_score),
                minimum_trade_size=max(1.0, round(available_capital * 0.001, 2)),
                maximum_trade_size=max(1.0, round(available_capital * 0.25, 2)),
            )
            position_size = sizing_rows[0] if sizing_rows else self._empty_position_size(candidate["symbol"])
            recommended_position_size = self._safe_float(position_size.get("recommended_position_size"), 0.0)

            strategy_memory_summary = self._safe_strategy_memory_summary()
            exit_plan = self.adaptive_exit_engine.recommend_exit(
                open_trade_context={
                    "trade_id": candidate["trade_id"],
                    "symbol": candidate["symbol"],
                    "entry_price": candidate["current_price"],
                },
                market_regime=market_regime,
                strategy_memory_summary=strategy_memory_summary,
                current_unrealized_pnl=0.0,
                holding_duration=0.0,
                volatility=volatility,
                trend_strength=trend_strength,
            )
            exit_confidence = self._safe_float(exit_plan.get("confidence"), 0.0)

            overall_confidence = self._compute_overall_confidence(
                market_confidence=market_confidence,
                strategy_score=strategy_score,
                allocation_weight=allocation_weight,
                portfolio_risk=portfolio_risk,
                exit_confidence=exit_confidence,
            )

            decision = self._derive_decision(
                market_regime=market_regime,
                strategy_score=strategy_score,
                allocation_weight=allocation_weight,
                position_size=recommended_position_size,
                portfolio_risk=portfolio_risk,
                concentration_score=concentration_score,
                exit_plan=exit_plan,
                overall_confidence=overall_confidence,
            )

            expected_reward, expected_risk = self._expected_risk_reward(
                current_price=candidate["current_price"],
                position_size=recommended_position_size,
                exit_plan=exit_plan,
            )
            approval_reason, rejection_reason = self._decision_reasons(decision)
            execution_status = "APPROVED" if decision == "ALLOW" else "NOT_APPROVED"
            normalized_signal_strength = round(max(0.0, min(1.0, strategy_score)), 8)
            normalized_confidence = round(max(0.0, min(1.0, overall_confidence)), 8)

            learning_context = {
                "learning_version": "v1",
                "confidence": normalized_confidence,
                "strategy": candidate["strategy"],
                "market_regime": market_regime,
                "features": {
                    "volatility": volatility,
                    "trend_strength": trend_strength,
                },
            }

            diagnostics = {
                "candidate": candidate["diagnostics"],
                "market_features": market_features,
                "strategy": strategy_details,
                "allocation_rows": allocation_rows,
                "correlation": correlation_summary,
                "concentration": concentration_summary,
                "sizing_rows": sizing_rows,
                "strategy_memory_summary": strategy_memory_summary,
            }

            result = IntelligenceDecision(
                timestamp=self._resolve_timestamp(candidate["market_snapshot"]),
                asset_class=candidate["asset_class"],
                symbol=candidate["symbol"],
                market_regime=market_regime,
                selected_strategy=candidate["strategy"],
                signal_strength=normalized_signal_strength,
                confidence=normalized_confidence,
                strategy_score=normalized_signal_strength,
                allocation=allocation,
                position_size=position_size,
                portfolio_risk=round(max(0.0, min(1.0, portfolio_risk)), 8),
                concentration_score=round(max(0.0, min(1.0, concentration_score)), 8),
                entry_decision=decision,
                exit_plan=exit_plan,
                expected_reward=expected_reward,
                expected_risk=expected_risk,
                approval_reason=approval_reason,
                rejection_reason=rejection_reason,
                execution_status=execution_status,
                learning_context=learning_context,
                overall_confidence=normalized_confidence,
                decision=decision,
                diagnostics=diagnostics,
            )
            if result.decision not in self._ALLOWED_DECISIONS:
                raise IntelligenceDecisionError("Invalid decision generated")
            return result
        except IntelligenceDecisionError:
            raise
        except Exception as exc:
            raise IntelligenceDecisionError(str(exc)) from exc

    def _validate_engines(self) -> None:
        required_engines = {
            "market_regime_engine": (self.market_regime_engine, "analyze_market"),
            "strategy_intelligence_engine": (self.strategy_intelligence_engine, "strategy_confidence"),
            "capital_allocation_engine": (self.capital_allocation_engine, "allocate"),
            "adaptive_position_sizing_engine": (self.adaptive_position_sizing_engine, "size_positions"),
            "portfolio_correlation_engine": (self.portfolio_correlation_engine, "analyze_portfolio"),
            "concentration_guard": (self.concentration_guard, "evaluate"),
            "adaptive_exit_engine": (self.adaptive_exit_engine, "recommend_exit"),
        }

        for name, (engine, method_name) in required_engines.items():
            if engine is None:
                raise IntelligenceDecisionError(f"Missing required engine: {name}")
            if not hasattr(engine, method_name):
                raise IntelligenceDecisionError(f"Missing required method {method_name} on {name}")

    def _resolve_strategy_recommendation(
        self,
        candidate: Mapping[str, Any],
        market_regime: str,
    ) -> tuple[float, dict[str, Any]]:
        strategy_id = candidate["strategy"]
        symbol = candidate["symbol"]
        strategy_confidence = self._safe_float(
            self.strategy_intelligence_engine.strategy_confidence(
                strategy_id,
                symbol=symbol,
                market_regime=market_regime,
            ),
            0.0,
        )

        best_symbol = self._safe_best_strategy(self.strategy_intelligence_engine.best_strategy_for_symbol(symbol))
        best_regime = self._safe_best_strategy(self.strategy_intelligence_engine.best_strategy_for_regime(market_regime))

        strategy_score = strategy_confidence
        if best_symbol and best_symbol.get("strategy_id") == strategy_id:
            strategy_score = max(strategy_score, self._safe_float(best_symbol.get("ranking_score"), 0.0))
        if best_regime and best_regime.get("strategy_id") == strategy_id:
            strategy_score = max(strategy_score, self._safe_float(best_regime.get("ranking_score"), 0.0))

        details = {
            "strategy_id": strategy_id,
            "strategy_confidence": round(max(0.0, min(1.0, strategy_confidence)), 8),
            "best_strategy_for_symbol": best_symbol,
            "best_strategy_for_regime": best_regime,
        }
        return strategy_score, details

    def _derive_decision(
        self,
        *,
        market_regime: str,
        strategy_score: float,
        allocation_weight: float,
        position_size: float,
        portfolio_risk: float,
        concentration_score: float,
        exit_plan: Mapping[str, Any],
        overall_confidence: float,
    ) -> str:
        exit_action = str(exit_plan.get("action") or "HOLD").strip().upper()
        portfolio_recommendation = str(exit_plan.get("portfolio_recommendation") or "").strip().upper()

        if portfolio_recommendation == "BLOCK" or exit_action == "STOP_LOSS" or portfolio_risk >= 0.8:
            return "BLOCK"

        if (
            portfolio_recommendation == "REDUCE_SIZE"
            or exit_action in {"REDUCE", "TAKE_PROFIT"}
            or concentration_score >= 0.5
            or allocation_weight <= 0.15
            or position_size <= 0.0
            or overall_confidence < 0.45
        ):
            if market_regime == "UNKNOWN" or strategy_score < 0.2 or overall_confidence < 0.25:
                return "DEFER"
            return "REDUCE_SIZE"

        if market_regime == "UNKNOWN" or strategy_score < 0.2:
            return "DEFER"

        return "ALLOW"

    def _compute_overall_confidence(
        self,
        *,
        market_confidence: float,
        strategy_score: float,
        allocation_weight: float,
        portfolio_risk: float,
        exit_confidence: float,
    ) -> float:
        score = (
            (market_confidence * 0.25)
            + (strategy_score * 0.30)
            + (allocation_weight * 0.15)
            + ((1.0 - portfolio_risk) * 0.15)
            + (exit_confidence * 0.15)
        )
        return max(0.0, min(1.0, score))

    def _resolve_risk_budget(self, portfolio_risk: float, concentration_score: float) -> float:
        risk_budget = 0.02
        if portfolio_risk >= 0.7 or concentration_score >= 0.7:
            risk_budget = 0.01
        elif portfolio_risk >= 0.45 or concentration_score >= 0.45:
            risk_budget = 0.015
        return risk_budget

    @staticmethod
    def _resolve_engine(engine: Any, expected_type: type[Any]) -> Any:
        if engine is IntelligenceOrchestrator._DEFAULT:
            return expected_type()
        return engine

    @staticmethod
    def _resolve_strategy_engine(engine: Any) -> Any:
        if engine is IntelligenceOrchestrator._DEFAULT:
            return _NullStrategyIntelligenceEngine()
        return engine

    @staticmethod
    def _normalize_candidate(trade_candidate: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(trade_candidate, Mapping):
            raise IntelligenceDecisionError("trade_candidate must be a mapping")

        required_fields = (
            "trade_id",
            "symbol",
            "asset_class",
            "direction",
            "strategy",
            "current_price",
            "market_snapshot",
            "portfolio_snapshot",
        )
        missing = [field for field in required_fields if field not in trade_candidate]
        if missing:
            raise IntelligenceDecisionError(f"trade_candidate missing required fields: {', '.join(missing)}")

        trade_id = str(trade_candidate.get("trade_id") or "").strip()
        symbol = str(trade_candidate.get("symbol") or "").strip().upper()
        asset_class = str(trade_candidate.get("asset_class") or "").strip().upper()
        direction = str(trade_candidate.get("direction") or "").strip().upper()
        strategy = str(trade_candidate.get("strategy") or "").strip()

        if not trade_id:
            raise IntelligenceDecisionError("trade_id must be non-empty")
        if not symbol:
            raise IntelligenceDecisionError("symbol must be non-empty")
        if not asset_class:
            raise IntelligenceDecisionError("asset_class must be non-empty")
        if direction not in {"LONG", "SHORT", "BUY", "SELL"}:
            raise IntelligenceDecisionError("direction must be LONG, SHORT, BUY, or SELL")
        if not strategy:
            raise IntelligenceDecisionError("strategy must be non-empty")

        try:
            current_price = float(trade_candidate.get("current_price"))
        except (TypeError, ValueError) as exc:
            raise IntelligenceDecisionError("current_price must be numeric") from exc
        if current_price <= 0.0:
            raise IntelligenceDecisionError("current_price must be positive")

        market_snapshot = trade_candidate.get("market_snapshot")
        portfolio_snapshot = trade_candidate.get("portfolio_snapshot")
        market_candles = IntelligenceOrchestrator._extract_market_candles(market_snapshot)
        portfolio_positions = IntelligenceOrchestrator._extract_portfolio_positions(portfolio_snapshot)

        return {
            "trade_id": trade_id,
            "symbol": symbol,
            "asset_class": asset_class,
            "direction": direction,
            "strategy": strategy,
            "current_price": current_price,
            "market_snapshot": market_snapshot,
            "market_candles": market_candles,
            "portfolio_snapshot": portfolio_snapshot,
            "portfolio_positions": portfolio_positions,
            "diagnostics": {
                "trade_id": trade_id,
                "symbol": symbol,
                "asset_class": asset_class,
                "direction": direction,
                "strategy": strategy,
                "current_price": current_price,
            },
        }

    @staticmethod
    def _extract_market_candles(market_snapshot: Any) -> list[dict[str, Any]]:
        if isinstance(market_snapshot, list):
            return [dict(row) if isinstance(row, Mapping) else row for row in market_snapshot]
        if isinstance(market_snapshot, Mapping):
            if "candles" in market_snapshot:
                candles = market_snapshot.get("candles")
                if not isinstance(candles, list):
                    raise IntelligenceDecisionError("market_snapshot.candles must be a list")
                return [dict(row) if isinstance(row, Mapping) else row for row in candles]
            return [dict(market_snapshot)]
        raise IntelligenceDecisionError("market_snapshot must be a mapping or list of candles")

    @staticmethod
    def _extract_portfolio_positions(portfolio_snapshot: Any) -> list[dict[str, Any]]:
        if isinstance(portfolio_snapshot, list):
            return [dict(row) if isinstance(row, Mapping) else row for row in portfolio_snapshot]
        if isinstance(portfolio_snapshot, Mapping):
            if "positions" in portfolio_snapshot:
                positions = portfolio_snapshot.get("positions")
                if not isinstance(positions, list):
                    raise IntelligenceDecisionError("portfolio_snapshot.positions must be a list")
                return [dict(row) if isinstance(row, Mapping) else row for row in positions]
            return [dict(portfolio_snapshot)] if portfolio_snapshot else []
        raise IntelligenceDecisionError("portfolio_snapshot must be a mapping or list of positions")

    @staticmethod
    def _resolve_available_capital(portfolio_snapshot: Any, current_price: float) -> float:
        if isinstance(portfolio_snapshot, Mapping):
            for field in ("available_capital", "buying_power", "cash_balance", "equity", "capital", "total_capital"):
                if field in portfolio_snapshot and portfolio_snapshot.get(field) is not None:
                    try:
                        value = float(portfolio_snapshot[field])
                        if value > 0.0:
                            return value
                    except (TypeError, ValueError):
                        continue

            positions = portfolio_snapshot.get("positions")
            if isinstance(positions, list) and positions:
                exposure_total = 0.0
                for position in positions:
                    if not isinstance(position, Mapping):
                        continue
                    for field in ("exposure_value", "market_value", "notional_value", "position_value", "current_value", "value", "quantity"):
                        if field in position and position.get(field) is not None:
                            try:
                                exposure_total += abs(float(position[field]))
                                break
                            except (TypeError, ValueError):
                                continue
                if exposure_total > 0.0:
                    return max(exposure_total, current_price)

        return max(current_price, 1.0)

    @staticmethod
    def _normalize_regime(market_features: Mapping[str, Any]) -> str:
        regime = market_features.get("market_regime")
        if regime is None:
            regime = market_features.get("regime")
        return str(regime or "UNKNOWN").strip().upper() or "UNKNOWN"

    @staticmethod
    def _safe_strategy_memory_summary() -> dict[str, Any]:
        return {}

    @staticmethod
    def _safe_best_strategy(value: Any) -> dict[str, Any] | None:
        if isinstance(value, Mapping):
            return dict(value)
        return None

    @staticmethod
    def _empty_allocation(symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "score": 0.0,
            "trade_count": 0,
            "realized_pnl": 0.0,
            "allocation_weight": 0.0,
            "allocation_amount": 0.0,
            "status": "NEUTRAL",
        }

    @staticmethod
    def _empty_position_size(symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "recommended_position_size": 0.0,
            "recommended_capital": 0.0,
            "confidence": 0.0,
            "sizing_reason": "allocation_not_approved",
            "sizing_status": "REJECTED",
        }

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _resolve_timestamp(market_snapshot: Any) -> str:
        if isinstance(market_snapshot, Mapping):
            value = str(market_snapshot.get("timestamp") or "").strip()
            if value:
                return value
        return "1970-01-01T00:00:00+00:00"

    @staticmethod
    def _expected_risk_reward(
        *,
        current_price: float,
        position_size: float,
        exit_plan: Mapping[str, Any],
    ) -> tuple[float, float]:
        take_profit = IntelligenceOrchestrator._safe_float(exit_plan.get("recommended_take_profit"), current_price)
        stop = IntelligenceOrchestrator._safe_float(exit_plan.get("recommended_stop"), current_price)
        reward_per_unit = max(0.0, take_profit - current_price)
        risk_per_unit = max(0.0, current_price - stop)
        expected_reward = round(reward_per_unit * max(0.0, position_size), 8)
        expected_risk = round(risk_per_unit * max(0.0, position_size), 8)
        return expected_reward, expected_risk

    @staticmethod
    def _decision_reasons(decision: str) -> tuple[str, str]:
        if decision == "ALLOW":
            return "all_intelligence_gates_passed", ""
        if decision == "REDUCE_SIZE":
            return "", "risk_or_exit_constraints_triggered"
        if decision == "DEFER":
            return "", "insufficient_confidence_or_unknown_regime"
        if decision == "BLOCK":
            return "", "risk_controls_blocked_entry"
        return "", "unknown_decision"
