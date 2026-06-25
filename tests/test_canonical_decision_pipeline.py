from __future__ import annotations

from backend.analytics.learning_pipeline_integration import LearningPipelineIntegration
from backend.analytics.regime_history_repository import RegimeHistoryRepository
from backend.analytics.strategy_memory_repository import StrategyMemoryRepository
from backend.analytics.trade_context_recorder import TradeContextRecorder
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository
from backend.intelligence.canonical_decision_pipeline import CanonicalDecisionPipeline
from backend.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
from backend.monitoring.alert_repository import AlertRepository
from backend.monitoring.notification_dispatcher import NotificationDispatcher
from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor


class _FakeMarketRegimeEngine:
    def analyze_market(self, candles):
        return {
            "market_regime": "TRENDING",
            "confidence": 0.9,
            "volatility": 0.02,
            "trend_strength": 0.7,
        }


class _FakeStrategyEngine:
    def strategy_confidence(self, strategy_id, **kwargs):
        return 0.85

    def best_strategy_for_symbol(self, symbol):
        return {"strategy_id": "alpha", "ranking_score": 0.85}

    def best_strategy_for_regime(self, regime):
        return {"strategy_id": "alpha", "ranking_score": 0.85}

    def strategy_memory_summary(self):
        return {"record_count": 1}


class _FakeCapitalAllocator:
    def allocate(self, ranking, **kwargs):
        row = ranking[0]
        return [
            {
                "symbol": row["symbol"],
                "score": 0.85,
                "trade_count": 1,
                "realized_pnl": 0.0,
                "allocation_weight": 0.25,
                "allocation_amount": 2500.0,
                "status": "PREFERRED",
            }
        ]


class _FakeSizer:
    def size_positions(self, allocations, **kwargs):
        return [
            {
                "symbol": allocations[0]["symbol"],
                "recommended_position_size": 150.0,
                "recommended_capital": 150.0,
                "confidence": kwargs["confidence"],
                "sizing_reason": "confidence_and_risk_adjusted",
                "sizing_status": "APPROVED",
            }
        ]


class _FakePortfolioCorrelation:
    def analyze_portfolio(self, positions):
        return {
            "concentration_score": 0.2,
        }


class _FakeConcentrationGuard:
    def evaluate(self, positions):
        return {
            "risk_score": 0.2,
            "concentration_score": 0.2,
            "recommendation": "ALLOW",
            "portfolio_summary": {"total_exposure": 1000.0},
        }


class _FakeExit:
    def recommend_exit(self, **kwargs):
        return {
            "trade_id": kwargs["open_trade_context"]["trade_id"],
            "symbol": kwargs["open_trade_context"]["symbol"],
            "action": "HOLD",
            "exit_reason": "TEST",
            "confidence": 0.8,
            "recommended_stop": 99.0,
            "recommended_take_profit": 101.0,
            "recommended_trailing_stop": 98.5,
            "max_hold_seconds": 3600,
        }


def _candidate() -> dict[str, object]:
    return {
        "trade_id": "trade-canonical-1",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "direction": "LONG",
        "strategy": "alpha",
        "current_price": 100.0,
        "market_snapshot": {
            "timestamp": "2026-06-24T12:00:00+00:00",
            "candles": [
                {"open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
                {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1005.0},
                {"open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "volume": 1010.0},
            ],
        },
        "portfolio_snapshot": {
            "available_capital": 10000.0,
            "positions": [{"symbol": "MSFT", "asset_class": "EQUITY", "exposure_value": 1000.0, "side": "LONG"}],
        },
    }


def _completed_trade() -> dict[str, object]:
    return {
        "trade_id": "trade-canonical-1",
        "timestamp_open": "2026-06-24T12:00:00+00:00",
        "timestamp_close": "2026-06-24T12:05:00+00:00",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "entry_price": 100.0,
        "exit_price": 101.0,
        "quantity": 1.0,
        "realized_pnl": 1.0,
        "holding_duration_seconds": 300.0,
        "strategy_id": "alpha",
        "market_regime": "TRENDING",
        "broker": "sim",
        "session": "ny-open",
        "volatility": 0.02,
        "trend_strength": 0.7,
        "confidence": 0.8,
    }


def test_canonical_pipeline_end_to_end(tmp_path) -> None:
    outcomes = TradeOutcomeRepository(tmp_path / "outcomes.json")
    regimes = RegimeHistoryRepository(tmp_path / "regimes.json")
    strategy_memory = StrategyMemoryRepository(tmp_path / "strategy_memory.json")
    outcomes.create_storage()
    regimes.create_storage()
    strategy_memory.create_storage()

    learning = LearningPipelineIntegration(
        trade_outcome_repository=outcomes,
        trade_context_recorder=TradeContextRecorder(),
        regime_history_repository=regimes,
        strategy_memory_repository=strategy_memory,
    )

    orchestrator = IntelligenceOrchestrator(
        market_regime_engine=_FakeMarketRegimeEngine(),
        strategy_intelligence_engine=_FakeStrategyEngine(),
        capital_allocation_engine=_FakeCapitalAllocator(),
        adaptive_position_sizing_engine=_FakeSizer(),
        portfolio_correlation_engine=_FakePortfolioCorrelation(),
        concentration_guard=_FakeConcentrationGuard(),
        adaptive_exit_engine=_FakeExit(),
    )
    alert_repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    dispatcher = NotificationDispatcher(storage_dir=str(tmp_path / "notifications"))
    supervisor = CSSRuntimeSupervisor(state_dir=str(tmp_path / "state"))

    pipeline = CanonicalDecisionPipeline(
        orchestrator=orchestrator,
        learning_pipeline=learning,
        alert_repository=alert_repo,
        notification_dispatcher=dispatcher,
        runtime_supervisor=supervisor,
    )

    result = pipeline.evaluate_cycle(
        trade_candidate=_candidate(),
        completed_trade=_completed_trade(),
        previous_canonical_decision={"market_regime": "RANGING"},
        rejection_streak=3,
    )

    canonical = result.canonical_decision
    assert canonical["market_regime"] == "TRENDING"
    assert canonical["selected_strategy"] == "alpha"
    assert canonical["entry_decision"] == canonical["decision"]
    assert canonical["confidence"] == canonical["overall_confidence"]
    assert "learning_context" in canonical

    # Learning consumes canonical decision fields instead of recalculating context.
    assert result.learning_result["trade_outcome"]["strategy_id"] == canonical["selected_strategy"]
    assert result.learning_result["trade_outcome"]["market_regime"] == canonical["market_regime"]
    assert result.learning_result["strategy_memory"]["confidence"] == canonical["confidence"]

    # Runtime supervisor stores the identical canonical object for cycle consumers.
    status = supervisor.get_status()
    assert status["last_canonical_decision"] == canonical
