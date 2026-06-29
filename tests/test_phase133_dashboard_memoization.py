from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from launcher.css_launcher_config import LauncherConfig
from launcher.css_mobile_launcher import app
import launcher.css_mobile_launcher as mobile


client = TestClient(app)


@pytest.fixture
def launcher_temp_dir():
    with tempfile.TemporaryDirectory() as td:
        original_artifacts = LauncherConfig.ARTIFACTS_DIR
        original_account = LauncherConfig.ACCOUNT_STATE_FILE
        original_session = LauncherConfig.SESSION_STATE_FILE
        original_ledger = LauncherConfig.CLOSED_TRADE_LEDGER_PATH
        original_supervisor = LauncherConfig.SUPERVISOR_STATE_FILE

        LauncherConfig.ARTIFACTS_DIR = os.path.join(td, "artifacts")
        LauncherConfig.ACCOUNT_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_account_state_pcnrass.json")
        LauncherConfig.SESSION_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_session_state_pcnrass.json")
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = os.path.join(td, "audit_logs", "closed_trades.jsonl")
        LauncherConfig.SUPERVISOR_STATE_FILE = os.path.join(td, "runtime", "supervisor", "css_runtime_supervisor_state.json")
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(LauncherConfig.CLOSED_TRADE_LEDGER_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(LauncherConfig.SUPERVISOR_STATE_FILE), exist_ok=True)

        yield td

        LauncherConfig.ARTIFACTS_DIR = original_artifacts
        LauncherConfig.ACCOUNT_STATE_FILE = original_account
        LauncherConfig.SESSION_STATE_FILE = original_session
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = original_ledger
        LauncherConfig.SUPERVISOR_STATE_FILE = original_supervisor


def _shared_pipeline_inputs() -> dict:
    return {
        "portfolio_intelligence": {
            "status": "OK",
            "portfolio_status": "HEALTHY",
            "intelligence_score": 95,
            "metrics": {"max_drawdown": 0.01, "largest_symbol_concentration": 0.25, "largest_asset_class_concentration": 0.45},
            "explainability": ["Portfolio evidence supports current allocation posture."],
        },
        "capital_rotation": {"status": "OK", "recommendation": "ROTATE_CAPITAL", "target_allocations": {"CASH": 10.0, "EQUITIES": 90.0}},
        "adaptive_portfolio": {
            "status": "OK",
            "adaptive_recommendation": "INCREASE_RISK",
            "risk_committee_status": "GREEN",
            "confidence": 90,
            "capital_rotation_action": "OPPORTUNISTIC",
            "primary_drivers": ["Portfolio intelligence is healthy."],
            "risk_flags": [],
        },
        "strategy_attribution": {
            "status": "OK",
            "advisory_only": True,
            "execution_allowed": False,
            "top_contributors": [{"symbol": "SPY", "pnl": 100.0}],
            "top_detractors": [],
            "recommendation": "EXPAND_WINNERS",
        },
        "regime_allocation": {"status": "OK", "detected_regime": "TRENDING_UP", "allocation_bias": "GROWTH"},
        "risk_committee": {
            "status": "OK",
            "committee_status": "GREEN",
            "committee_decision": "APPROVE_ADVISORY",
            "confidence": 90,
            "concerns": [],
        },
        "quantitative_metrics": {
            "status": "OK",
            "metrics": {"rolling_sharpe": 1.0, "rolling_sortino": 1.2, "max_drawdown": 0.01, "volatility": 0.02},
            "sample_size": 4,
        },
        "market_regime_intelligence": {"status": "OK", "detected_regime": "TRENDING_UP", "risk_bias": "OPPORTUNISTIC"},
        "policy_profile": {"status": "OK", "active_profile": "GROWTH", "profile": {"allowed_recommendation_ceiling": "INCREASE_RISK"}},
        "recommendation_tracker": {"status": "OK", "total_recommendations": 0, "advisory_only": True},
        "conflicting_signals": [],
        "consistency": {"status": "OK", "consistent": True, "conflicts": [], "recommended_resolution": "Proceed with advisory package.", "advisory_only": True},
    }


def test_dashboard_uses_single_shared_decision_pipeline(monkeypatch, launcher_temp_dir) -> None:
    calls = {"count": 0}
    shared_inputs = _shared_pipeline_inputs()

    def fake_pipeline_inputs():
        calls["count"] += 1
        return shared_inputs

    monkeypatch.setattr(mobile, "_portfolio_decision_inputs", fake_pipeline_inputs)
    monkeypatch.setattr(mobile, "get_tradeable_symbols_feed", lambda *args, **kwargs: {"symbols": []})
    monkeypatch.setattr(mobile, "get_grouped_trading_universe_feed", lambda *args, **kwargs: {"groups": []})
    monkeypatch.setattr(mobile, "get_top_opportunities_feed", lambda *args, **kwargs: {"top_opportunities": []})
    monkeypatch.setattr(
        mobile,
        "get_portfolio_summary_feed",
        lambda: {
            "status": "OK",
            "summary": {
                "portfolio_health": "HEALTHY",
                "cash": 1000,
                "exposure": 0,
                "diversification": "N/A",
                "risk_score": 0,
                "current_allocation": {},
                "recommended_allocation": {},
            },
        },
    )
    monkeypatch.setattr(mobile, "get_strategy_evolution_feed", lambda: {"status": "INSUFFICIENT_DATA", "minimum_history": 20, "top_strategies": [], "declining_strategies": [], "promotions": [], "retirements": [], "recommended_strategy_weights": {}})
    monkeypatch.setattr(mobile, "get_portfolio_allocation_feed", lambda: {"status": "UNAVAILABLE", "allocations": [], "diversification_metrics": {}})
    monkeypatch.setattr(mobile, "get_opportunity_feed", lambda: {"top_opportunities": [], "updated_at": None})

    response = client.get("/mobile")

    assert response.status_code == 200
    assert calls["count"] == 1
    html = response.text
    assert 'id="portfolio-decision-card"' in html
    assert 'id="adaptive-portfolio-card"' in html
    assert 'id="quantitative-intelligence-card"' in html
    assert not os.path.exists(os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio", "portfolio_decision_packages.json"))
