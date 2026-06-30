from __future__ import annotations

from backend.monitoring.runtime_health_aggregator import RuntimeHealthAggregator
from backend.portfolio.adaptive_portfolio_manager import AdaptivePortfolioManager
from backend.portfolio.capital_rotation_engine import CapitalRotationEngine
from backend.portfolio.portfolio_intelligence_engine import PortfolioIntelligenceEngine
from backend.validation.validation_readiness_engine import ValidationReadinessEngine


def test_phase135c_no_exposure_components_return_limited_not_broken() -> None:
    intelligence = PortfolioIntelligenceEngine().analyze([], {})
    rotation = CapitalRotationEngine().recommend([], intelligence)
    adaptive = AdaptivePortfolioManager().evaluate(intelligence, rotation, {"status": "RUNNING"})

    assert intelligence["status"] == "LIMITED"
    assert intelligence["portfolio_status"] == "NO_PORTFOLIO"
    assert rotation["status"] == "LIMITED"
    assert rotation["candidate_allocations"] == []
    assert adaptive["status"] == "LIMITED"
    assert adaptive["adaptive_recommendation"] == "AWAIT_PORTFOLIO_BUILD"
    assert adaptive["risk_committee_status"] == "GREEN"


def test_phase135c_validation_treats_no_portfolio_as_caution_not_blocker() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "RED", "missing_inputs": ["quantitative_metrics"]},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={"snapshot_status": "PARTIAL", "missing_components": ["quantitative_metrics"]},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "NO_PORTFOLIO"},
    )

    assert result["readiness_status"] == "READY_WITH_CAUTION"
    assert result["portfolio_lifecycle_state"] == "NO_PORTFOLIO"
    assert result["blockers"] == []
    assert "portfolio_lifecycle_no_portfolio" in result["warnings"]


def test_phase135c_runtime_health_distinguishes_no_portfolio_and_broken_pipeline() -> None:
    healthy = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "NO_PORTFOLIO"},
    )
    broken = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={"status": "DATA UNAVAILABLE", "portfolio_state": "BROKEN_PIPELINE"},
    )

    assert healthy["runtime_health"] == "GREEN"
    assert healthy["portfolio_lifecycle_state"] == "NO_PORTFOLIO"
    assert broken["runtime_health"] == "RED"
    assert broken["portfolio_lifecycle_state"] == "BROKEN_PIPELINE"
