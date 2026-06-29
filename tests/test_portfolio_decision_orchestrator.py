from __future__ import annotations

import os

from backend.portfolio.portfolio_decision_orchestrator import DecisionPackageStore, PortfolioDecisionOrchestrator


def _inputs(status: str = "GREEN") -> dict:
    committee_status = status
    adaptive_status = status
    recommendation = "INCREASE_RISK" if status == "GREEN" else ("MAINTAIN" if status == "AMBER" else "PAUSE_NEW_TRADES")
    return {
        "portfolio_intelligence": {
            "status": "OK",
            "portfolio_status": "HEALTHY",
            "intelligence_score": 91,
            "metrics": {"max_drawdown": 0.02, "largest_symbol_concentration": 0.25},
        },
        "capital_rotation": {"status": "OK", "target_allocations": {"CASH": 10.0, "EQUITIES": 90.0}},
        "adaptive_portfolio": {
            "status": "OK",
            "adaptive_recommendation": recommendation,
            "risk_committee_status": adaptive_status,
            "confidence": 88,
        },
        "strategy_attribution": {"status": "OK", "recommendation": "EXPAND_WINNERS"},
        "regime_allocation": {"status": "OK", "allocation_bias": "GROWTH"},
        "risk_committee": {
            "status": "OK",
            "committee_status": committee_status,
            "committee_decision": "APPROVE_ADVISORY" if status != "RED" else "PAUSE_NEW_TRADES",
            "confidence": 88,
        },
        "quantitative_metrics": {
            "status": "OK",
            "metrics": {"rolling_sharpe": 1.2, "rolling_sortino": 1.5, "max_drawdown": 0.02, "volatility": 0.01},
            "sample_size": 5,
        },
        "market_regime_intelligence": {"status": "OK", "detected_regime": "TRENDING_UP", "risk_bias": "OPPORTUNISTIC"},
        "policy_profile": {"status": "OK", "active_profile": "GROWTH", "profile": {"allowed_recommendation_ceiling": "INCREASE_RISK"}},
        "recommendation_tracker": {"status": "OK", "total_recommendations": 0},
        "conflicting_signals": [],
    }


def test_portfolio_decision_orchestrator_green_path() -> None:
    result = PortfolioDecisionOrchestrator().orchestrate(_inputs(), timestamp="2026-06-29T00:00:00Z")

    assert result["overall_status"] == "GREEN"
    assert result["portfolio_recommendation"] == "INCREASE_RISK"
    assert result["confidence"] == 88
    assert result["policy_profile"] == "GROWTH"
    assert result["advisory_only"] is True


def test_portfolio_decision_orchestrator_amber_and_red_paths() -> None:
    amber = PortfolioDecisionOrchestrator().orchestrate(_inputs("AMBER"), timestamp="2026-06-29T00:00:00Z")
    red = PortfolioDecisionOrchestrator().orchestrate(_inputs("RED"), timestamp="2026-06-29T00:00:00Z")

    assert amber["overall_status"] == "AMBER"
    assert amber["confidence"] <= 70
    assert red["overall_status"] == "RED"
    assert red["portfolio_recommendation"] == "PAUSE_NEW_TRADES"
    assert red["confidence"] <= 30


def test_portfolio_decision_orchestrator_missing_data_fails_closed() -> None:
    result = PortfolioDecisionOrchestrator().orchestrate({"portfolio_intelligence": {}}, timestamp="2026-06-29T00:00:00Z")

    assert result["overall_status"] == "RED"
    assert result["portfolio_recommendation"] == "PAUSE_NEW_TRADES"
    assert "adaptive_portfolio" in result["missing_inputs"]


def test_decision_package_store_persistence_and_corruption_recovery(tmp_path) -> None:
    store = DecisionPackageStore(str(tmp_path))
    package = PortfolioDecisionOrchestrator().orchestrate(_inputs(), timestamp="2026-06-29T00:00:00Z")

    appended = store.append(package)
    lookup = store.lookup(package["decision_id"])
    summary = store.summary()

    assert appended["count"] == 1
    assert lookup["decision"]["decision_id"] == package["decision_id"]
    assert summary["status_counts"]["GREEN"] == 1

    with open(store.path, "w", encoding="utf-8") as handle:
        handle.write("{bad json")

    assert store.list_recent()["decisions"] == []
    assert store.summary()["total_decisions"] == 0
    assert os.path.exists(store.path)
