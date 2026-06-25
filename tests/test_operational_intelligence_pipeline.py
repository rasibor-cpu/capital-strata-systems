from __future__ import annotations

from pathlib import Path

from backend.analytics.improvement_recommendation_engine import ImprovementRecommendationEngine
from backend.analytics.opportunity_cost_engine import OpportunityCostEngine
from backend.analytics.performance_attribution_engine import PerformanceAttributionEngine
from backend.analytics.strategy_league_table import StrategyLeagueTable
from backend.analytics.trade_forensics_engine import TradeForensicsEngine
from backend.validation.marathon_certification_engine import MarathonCertificationEngine
from backend.validation.marathon_evidence_repository import MarathonEvidenceRepository
from backend.validation.marathon_health_monitor import MarathonHealthMonitor
from backend.validation.marathon_runtime_statistics import MarathonRuntimeStatistics
from backend.validation.marathon_summary_report import MarathonSummaryReport


def _snapshot(cycle_number: int, equity: float, pnl: float) -> dict[str, object]:
    return {
        "cycle_number": cycle_number,
        "timestamp": f"2026-06-24T12:00:0{cycle_number}+00:00",
        "runtime_duration_seconds": 60.0,
        "cycle_duration_seconds": 60.0,
        "heartbeat_age_seconds": 2.0,
        "restart_count": 0,
        "recovery_count": 0,
        "alert_count": 0,
        "trade_count": 2,
        "approved_trades": 2,
        "blocked_trades": 0,
        "capital": equity,
        "equity": equity,
        "drawdown": max(0.0, 100000.0 - equity),
        "decision_latency_seconds": 0.2,
        "runtime_latency_seconds": 0.4,
        "trade_statistics": {"trade_count": 2, "realized_pnl": pnl},
    }


def test_unified_operational_report(tmp_path: Path) -> None:
    repository = MarathonEvidenceRepository(tmp_path / "evidence.json")
    repository.record_event({"event_type": "heartbeat", "payload": {"age_seconds": 2.0}})
    repository.record_event({"event_type": "strategy_selection", "payload": {"strategy_id": "alpha"}})
    repository.record_event({"event_type": "regime_transition", "payload": {"from": "TRENDING", "to": "RANGING"}})
    repository.record_snapshot(_snapshot(1, 100020.0, 12.0))
    repository.record_snapshot(_snapshot(2, 100030.0, 14.0))

    evidence = repository.summarize()
    health = MarathonHealthMonitor().evaluate({**evidence, "runtime_stability_metric": 0.95, "memory_growth_metric": 0.05, "consecutive_failures": 0})
    runtime = MarathonRuntimeStatistics().compute(evidence)
    certification = MarathonCertificationEngine().certify(evidence, health_summary=health, runtime_statistics=runtime)

    trades = [
        {"trade_id": "t1", "strategy_id": "alpha", "market_regime": "TRENDING", "confidence": 0.8, "quality_score": 88.0, "position_size": 1200.0, "capital_allocation": 2000.0, "holding_time_seconds": 1800.0, "realized_pnl": 12.0, "expected_pnl": 10.0, "entry_reason": "trend", "exit_reason": "take_profit", "asset_class": "EQUITY", "timestamp_close": "2026-06-24T12:30:00+00:00"},
        {"trade_id": "t2", "strategy_id": "beta", "market_regime": "RANGING", "confidence": 0.4, "quality_score": 44.0, "position_size": 4000.0, "capital_allocation": 3000.0, "holding_time_seconds": 7200.0, "realized_pnl": -4.0, "expected_pnl": -2.0, "entry_reason": "range", "exit_reason": "stop_loss", "asset_class": "EQUITY", "timestamp_close": "2026-06-24T13:30:00+00:00"},
    ]
    trade_forensics = TradeForensicsEngine().explain_trades(trades)
    attribution = PerformanceAttributionEngine().attribute(trades)
    league = StrategyLeagueTable().rank_strategies([
        {"strategy_id": "alpha", "win_rate": 0.7, "profit_factor": 1.8, "expectancy": 0.8, "stability": 0.9, "drawdown": 0.08, "sample_size": 20, "recent_trend": 0.4},
        {"strategy_id": "beta", "win_rate": 0.4, "profit_factor": 0.9, "expectancy": -0.1, "stability": 0.5, "drawdown": 0.2, "sample_size": 12, "recent_trend": -0.2},
    ])
    opportunity_cost = OpportunityCostEngine().analyze_rejected_trades([
        {"trade_id": "t3", "rejection_reason": "LOW_CONFIDENCE", "confidence": 0.4, "expected_pnl": 8.0, "realized_pnl": 9.0},
    ])
    recommendations = ImprovementRecommendationEngine().recommend(
        performance_summary={"win_rate": 0.6, "profit_factor": 1.2, "max_drawdown": runtime["uptime_pct"], "exit_confidence": 0.55},
        strategy_league_table=league,
        opportunity_cost=opportunity_cost,
        attribution=attribution,
        health_summary=health,
    )

    report = MarathonSummaryReport().build_report(
        marathon_evidence=evidence,
        health_summary=health,
        runtime_statistics=runtime,
        certification_summary=certification,
        trade_forensics=trade_forensics,
        attribution=attribution,
        strategy_league_table=league,
        opportunity_cost=opportunity_cost,
        improvement_recommendations=recommendations,
    )

    assert report["unified_operational_report"]["certification_summary"]["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert report["trade_forensics"][0]["trade_id"] == "t1"
    assert report["strategy_league_table"][0]["strategy_id"] == "alpha"
    assert report["opportunity_cost"]["summary"]["rejected_trade_count"] == 1
