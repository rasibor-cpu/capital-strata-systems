from __future__ import annotations

from pathlib import Path

from backend.analytics.adaptive_calibration_engine import AdaptiveCalibrationEngine
from backend.analytics.opportunity_ranking_engine import OpportunityRankingEngine
from backend.analytics.performance_analytics_engine import PerformanceAnalyticsEngine
from backend.analytics.performance_reporting_engine import PerformanceReportingEngine
from backend.analytics.trade_quality_scoring_engine import TradeQualityScoringEngine
from backend.validation.live_readiness_gate import LiveReadinessGate


def _trade(trade_id, pnl, score):
    return {
        "trade_id": trade_id,
        "symbol": "AAPL" if trade_id == "t1" else "MSFT",
        "asset_class": "EQUITY",
        "strategy_id": "alpha",
        "market_regime": "TRENDING",
        "realized_pnl": pnl,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "quantity": 10.0,
        "holding_duration_minutes": 15.0,
        "is_closed": True,
        "quality_score": score,
    }


def test_integrated_production_pipeline(tmp_path: Path) -> None:
    scorer = TradeQualityScoringEngine()
    ranker = OpportunityRankingEngine()
    performance = PerformanceAnalyticsEngine()
    calibration = AdaptiveCalibrationEngine()
    reporting = PerformanceReportingEngine()

    scored = scorer.score_candidates([
        {
            "trade_id": "t1",
            "symbol": "AAPL",
            "asset_class": "EQUITY",
            "market_regime": "TRENDING",
            "strategy_score": 0.9,
            "replay_confidence": 0.9,
            "concentration_risk": 0.1,
            "allocation_weight": 0.2,
            "allocation_amount": 2000.0,
            "available_capital": 10000.0,
            "recommended_position_size": 1500.0,
            "exit_action": "TRAIL",
            "exit_confidence": 0.85,
            "risk_reward": 2.1,
        },
        {
            "trade_id": "t2",
            "symbol": "MSFT",
            "asset_class": "EQUITY",
            "market_regime": "RANGING",
            "strategy_score": 0.45,
            "replay_confidence": 0.4,
            "concentration_risk": 0.5,
            "allocation_weight": 0.1,
            "allocation_amount": 1000.0,
            "available_capital": 10000.0,
            "recommended_position_size": 500.0,
            "exit_action": "WATCH",
            "exit_confidence": 0.5,
            "risk_reward": 0.9,
        },
    ])
    ranked = ranker.rank(scored, top_n=2)
    metrics = performance.analyze([_trade("t1", 0.8, scored[0]["quality_score"]), _trade("t2", -0.2, scored[1]["quality_score"])])
    calibration_result = calibration.recommend({"win_rate": 0.4, "profit_factor": metrics["profit_factor"], "max_drawdown": metrics["max_drawdown"], "recovery_factor": metrics["recovery_factor"], "consecutive_losses": metrics["consecutive_losses"], "concentration_score": 0.2, "strategy_strength": 0.6, "regime_strength": 0.5}, calibration_state={"trade_quality_weights": [0.12] * 8, "strategy_weighting": [0.1] * 6, "regime_sensitivity": [1.0] * 7})
    reports = reporting.build_reports(
        performance_metrics=metrics,
        calibration_report=calibration_result,
        trade_quality_report={"trade_quality_summary": {item["trade_id"]: item["quality_score"] for item in scored}},
        runtime_health_report={"runtime_healthy": True},
        recovery_report={"operational": True},
        profitability_report=metrics,
        learning_report={"learning_status": "READY"},
        strategy_ranking_report={"strategy_rankings": ranked},
    )

    evidence = tmp_path / "artifacts" / "marathon" / "evidence.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("evidence", encoding="utf-8")

    gate = LiveReadinessGate(repository_root=Path.cwd(), evidence_path=evidence, repository_clean_probe=lambda: True)
    readiness = gate.evaluate(
        trades=[_trade("t1", 0.8, scored[0]["quality_score"]), _trade("t2", -0.2, scored[1]["quality_score"])],
        calibration_summary=calibration_result,
        tests_passing=True,
        runtime_healthy=True,
        alerts_operational=True,
        recovery_operational=True,
        learning_operational=True,
        calibration_complete=True,
    )

    assert reports["profitability_report"]["profitability_summary"]["trade_count"] == 2
    assert readiness.readiness_status == "GO"
