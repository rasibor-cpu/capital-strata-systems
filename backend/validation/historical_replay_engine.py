from __future__ import annotations

from typing import Any, Iterable, Mapping

from backend.analytics.adaptive_exit_engine import AdaptiveExitEngine
from backend.analytics.adaptive_position_sizing import AdaptivePositionSizingEngine
from backend.analytics.capital_allocation_engine import CapitalAllocationEngine
from backend.analytics.concentration_guard import ConcentrationGuard
from backend.analytics.market_regime_engine import MarketRegimeEngine
from backend.analytics.portfolio_correlation_engine import PortfolioCorrelationEngine
from backend.intelligence.intelligence_orchestrator import IntelligenceOrchestrator

from .replay_models import (
    HistoricalReplayRecord,
    ReplayDecision,
    ReplayModelsError,
    ReplayRunResult,
)
from .replay_statistics import ReplayStatistics, build_replay_statistics, ReplayStatisticsError


class HistoricalReplayEngineError(RuntimeError):
    """Fail-closed exception for replay execution failures."""


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


class HistoricalReplayEngine:
    """Deterministic replay runner for historical CSS intelligence decisions."""

    def __init__(
        self,
        *,
        orchestrator: IntelligenceOrchestrator | None = None,
        market_regime_engine: MarketRegimeEngine | None = None,
        strategy_intelligence_engine: Any | None = None,
        capital_allocation_engine: CapitalAllocationEngine | None = None,
        adaptive_position_sizing_engine: AdaptivePositionSizingEngine | None = None,
        portfolio_correlation_engine: PortfolioCorrelationEngine | None = None,
        concentration_guard: ConcentrationGuard | None = None,
        adaptive_exit_engine: AdaptiveExitEngine | None = None,
    ) -> None:
        self.market_regime_engine = market_regime_engine or MarketRegimeEngine()
        self.strategy_intelligence_engine = strategy_intelligence_engine or _NullStrategyIntelligenceEngine()
        self.capital_allocation_engine = capital_allocation_engine or CapitalAllocationEngine()
        self.adaptive_position_sizing_engine = adaptive_position_sizing_engine or AdaptivePositionSizingEngine()
        self.portfolio_correlation_engine = portfolio_correlation_engine or PortfolioCorrelationEngine()
        self.concentration_guard = concentration_guard or ConcentrationGuard()
        self.adaptive_exit_engine = adaptive_exit_engine or AdaptiveExitEngine()

        if orchestrator is None:
            orchestrator = IntelligenceOrchestrator(
                market_regime_engine=self.market_regime_engine,
                strategy_intelligence_engine=self.strategy_intelligence_engine,
                capital_allocation_engine=self.capital_allocation_engine,
                adaptive_position_sizing_engine=self.adaptive_position_sizing_engine,
                portfolio_correlation_engine=self.portfolio_correlation_engine,
                concentration_guard=self.concentration_guard,
                adaptive_exit_engine=self.adaptive_exit_engine,
            )
        self.orchestrator = orchestrator

    def replay(self, history: Iterable[Mapping[str, Any]] | None) -> list[ReplayDecision]:
        records = self._normalize_history(history)
        if not records:
            return []

        decisions: list[ReplayDecision] = []
        for record in records:
            selected_strategy, strategy_diagnostics = self._select_strategy(record)
            replay_candidate = record.trade_candidate
            effective_candidate = {
                "trade_id": replay_candidate.trade_id,
                "symbol": replay_candidate.symbol,
                "asset_class": replay_candidate.asset_class,
                "direction": replay_candidate.direction,
                "strategy": selected_strategy,
                "current_price": replay_candidate.current_price,
                "market_snapshot": replay_candidate.market_snapshot,
                "portfolio_snapshot": replay_candidate.portfolio_snapshot,
            }

            orchestration_result = self.orchestrator.decide(effective_candidate)
            canonical_decision = orchestration_result.to_dict()
            decisions.append(
                ReplayDecision(
                    timestamp=record.timestamp,
                    symbol=replay_candidate.symbol,
                    market_regime=orchestration_result.market_regime,
                    selected_strategy=selected_strategy,
                    allocation=orchestration_result.allocation,
                    position_size=orchestration_result.position_size,
                    risk_score=orchestration_result.portfolio_risk,
                    confidence=orchestration_result.confidence,
                    decision=orchestration_result.entry_decision,
                    exit_plan=orchestration_result.exit_plan,
                    diagnostics={
                        **orchestration_result.diagnostics,
                        "selected_strategy": selected_strategy,
                        "strategy_diagnostics": strategy_diagnostics,
                        "historical_market_event": record.market_event.__dict__,
                        "completed_trade": record.completed_trade.__dict__ if record.completed_trade else None,
                    },
                    canonical_decision=canonical_decision,
                )
            )

        return decisions

    def replay_with_statistics(self, history: Iterable[Mapping[str, Any]] | None) -> ReplayRunResult:
        decisions = self.replay(history)
        statistics = build_replay_statistics(decisions).to_dict()
        return ReplayRunResult(decisions=decisions, statistics=statistics)

    def summarize(self, decisions: Iterable[ReplayDecision | Mapping[str, Any]] | None) -> ReplayStatistics:
        try:
            return build_replay_statistics(decisions or [])
        except (ReplayModelsError, ReplayStatisticsError) as exc:
            raise HistoricalReplayEngineError(str(exc)) from exc

    def _select_strategy(self, record: HistoricalReplayRecord) -> tuple[str, dict[str, Any]]:
        symbol = record.trade_candidate.symbol
        market_regime = self.market_regime_engine.analyze_market(record.trade_candidate.market_snapshot.get("candles", []))
        market_regime_name = str(
            market_regime.get("market_regime") or market_regime.get("regime") or "UNKNOWN"
        ).strip().upper() or "UNKNOWN"

        ranked: list[dict[str, Any]] = []
        try:
            ranked = self.strategy_intelligence_engine.rank_strategies_by_context(
                symbol=symbol,
                asset_class=record.trade_candidate.asset_class,
                market_regime=market_regime_name,
            )
        except Exception as exc:
            raise HistoricalReplayEngineError(str(exc)) from exc

        if ranked:
            top = ranked[0]
            selected_strategy = str(top.get("strategy_id") or record.trade_candidate.strategy).strip() or record.trade_candidate.strategy
            diagnostics = {
                "market_regime": market_regime_name,
                "ranked_strategies": ranked,
                "strategy_confidence": top.get("confidence", 0.0),
            }
            return selected_strategy, diagnostics

        diagnostics = {
            "market_regime": market_regime_name,
            "ranked_strategies": [],
            "strategy_confidence": 0.0,
        }
        return record.trade_candidate.strategy, diagnostics

    @staticmethod
    def _normalize_history(history: Iterable[Mapping[str, Any]] | None) -> list[HistoricalReplayRecord]:
        if history is None:
            raise HistoricalReplayEngineError("history must not be None")
        if not isinstance(history, Iterable):
            raise HistoricalReplayEngineError("history must be iterable")

        normalized: list[HistoricalReplayRecord] = []
        try:
            for item in history:
                normalized.append(HistoricalReplayRecord.from_mapping(item))
        except (ReplayModelsError, TypeError, ValueError) as exc:
            raise HistoricalReplayEngineError(str(exc)) from exc
        return normalized
