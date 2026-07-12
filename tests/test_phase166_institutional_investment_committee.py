from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.investment_committee.investment_committee import (
    InstitutionalInvestmentCommittee,
    build_institutional_investment_committee_report,
)
from dashboard.runtime.api_bridge import create_app, get_institutional_investment_committee_payload
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.web.web_app import _dashboard_page


def _context(**overrides):
    data = {
        "available_capital": 100000.0,
        "deployable_capital": 60000.0,
        "equity": 125000.0,
        "max_approved_opportunities": 3,
        "max_expected_drawdown": 0.08,
        "max_risk_budget_consumption": 0.35,
        "max_sector_concentration": 0.40,
        "max_portfolio_correlation": 0.75,
        "min_committee_score": 60.0,
        "min_approval_score": 75.0,
        "min_low_priority_score": 65.0,
        "market_health": 0.85,
        "operational_readiness": 0.90,
        "exposure_by_sector": {},
        "advisory_only": True,
        "execution_allowed": False,
    }
    data.update(overrides)
    return data


def _opportunity(symbol="BTC-USD", **overrides):
    data = {
        "opportunity_id": f"opp-{symbol}",
        "symbol": symbol,
        "asset_class": "CRYPTO",
        "sector": "DIGITAL",
        "strategy": "trend",
        "broker": "COINBASE",
        "requested_capital": 10000.0,
        "expected_return": 0.035,
        "probability_of_success": 0.82,
        "expected_drawdown": 0.025,
        "expected_holding_period": 3,
        "capital_efficiency": 0.92,
        "portfolio_correlation": 0.22,
        "sector_concentration": 0.12,
        "asset_allocation_impact": 0.78,
        "regime_suitability": 0.88,
        "liquidity": 0.91,
        "spread_quality": 0.86,
        "execution_cost": 0.04,
        "volatility": 0.24,
        "risk_budget_consumption": 0.16,
        "strategy_confidence": 0.84,
        "signal_quality": 0.87,
        "historical_similarity": 0.79,
        "decision_confidence": 0.86,
        "operational_readiness": 0.90,
        "market_health": 0.86,
    }
    data.update(overrides)
    return data


def _state_with_opportunities(opportunities):
    state = DashboardState()
    state.last_scan_results["opportunities"] = opportunities
    state.last_scan_results["account_summary"] = {
        "cash_balance": 100000.0,
        "buying_power": 100000.0,
        "total_equity": 125000.0,
        "broker": "DEMO",
    }
    state.last_scan_results["risk_summary"] = {
        "max_committee_approved_opportunities": 2,
        "max_expected_drawdown": 0.08,
        "min_committee_score": 60,
    }
    state.last_scan_results["position_state"] = {"positions": []}
    state.broker_state.selected_broker = "DEMO"
    state.broker_state.api_health = "GREEN"
    return state


def test_phase166_single_trade_approval():
    report = InstitutionalInvestmentCommittee().evaluate([_opportunity()], portfolio_context=_context())

    assert report["decision"] == "APPROVED"
    assert report["committee_score"] >= 75
    assert report["evaluations"][0]["recommended_capital"] > 0
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True


def test_phase166_trade_rejection_for_insufficient_edge():
    report = InstitutionalInvestmentCommittee().evaluate(
        [_opportunity(expected_return=-0.01, probability_of_success=0.35)],
        portfolio_context=_context(),
    )

    assert report["decision"] == "INSUFFICIENT_EDGE"
    assert "INSUFFICIENT_EDGE" in report["blockers"]
    assert report["capital_plan"] == []


def test_phase166_portfolio_conflict_blocks_allocation():
    report = InstitutionalInvestmentCommittee().evaluate(
        [_opportunity(portfolio_correlation=0.92)],
        portfolio_context=_context(),
    )

    assert report["decision"] == "PORTFOLIO_CONFLICT"
    assert "PORTFOLIO_CONFLICT" in report["blockers"]


def test_phase166_risk_limit_exceeded_blocks_allocation():
    report = InstitutionalInvestmentCommittee().evaluate(
        [_opportunity(expected_drawdown=0.20, risk_budget_consumption=0.55)],
        portfolio_context=_context(),
    )

    assert report["decision"] == "RISK_LIMIT_EXCEEDED"
    assert "RISK_LIMIT_EXCEEDED" in report["blockers"]


def test_phase166_low_confidence_waits_or_rejects():
    report = InstitutionalInvestmentCommittee().evaluate(
        [
            _opportunity(
                strategy_confidence=0.20,
                signal_quality=0.25,
                historical_similarity=0.20,
                decision_confidence=0.20,
                probability_of_success=0.42,
            )
        ],
        portfolio_context=_context(),
    )

    assert report["decision"] in {"WAIT", "REJECT", "INSUFFICIENT_EDGE"}
    assert report["capital_plan"] == []


def test_phase166_high_confidence_ranks_above_weaker_trade():
    report = InstitutionalInvestmentCommittee().evaluate(
        [
            _opportunity("ETH-USD", expected_return=0.018, decision_confidence=0.62, capital_efficiency=0.52),
            _opportunity("BTC-USD", expected_return=0.038, decision_confidence=0.90, capital_efficiency=0.95),
        ],
        portfolio_context=_context(),
    )

    assert report["evaluations"][0]["opportunity"]["symbol"] == "BTC-USD"
    assert report["evaluations"][0]["capital_rank"] == 1


def test_phase166_capital_displacement_and_best_use_of_capital():
    report = InstitutionalInvestmentCommittee().evaluate(
        [
            _opportunity("BTC-USD", expected_return=0.039),
            _opportunity("ETH-USD", expected_return=0.037),
            _opportunity("SOL-USD", expected_return=0.036),
        ],
        portfolio_context=_context(max_approved_opportunities=1, deployable_capital=10000.0),
    )

    decisions = {row["opportunity"]["symbol"]: row["decision"] for row in report["evaluations"]}
    assert list(decisions.values()).count("APPROVED") == 1
    assert "CAPITAL_BETTER_DEPLOYED" in decisions.values()
    assert any(row["capital_displacement"] for row in report["evaluations"])


def test_phase166_committee_explanation_is_institutional_and_advisory():
    report = InstitutionalInvestmentCommittee().evaluate([_opportunity()], portfolio_context=_context())
    explanation = report["evaluations"][0]["explanation"]

    assert "Expected return" in explanation
    assert "expected drawdown" in explanation
    assert "capital efficiency" in explanation
    assert "advisory only" in explanation


def test_phase166_dashboard_serialization_contains_committee_section():
    state = _state_with_opportunities([_opportunity()])
    payload = build_frontend_payload(state)
    section = payload["sections"]["institutional_investment_committee"]

    assert section["decision"] == "APPROVED"
    assert section["committee_score"] >= 75
    assert section["execution_allowed"] is False
    assert section["top_opportunities"][0]["symbol"] == "BTC-USD"


def test_phase166_runtime_api_serialization():
    state = _state_with_opportunities([_opportunity()])
    client = TestClient(create_app(lambda: state))

    response = client.get("/api/v1/institutional-investment-committee")

    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "institutional_investment_committee"
    assert payload["decision"] == "APPROVED"
    assert payload["execution_allowed"] is False


def test_phase166_api_helper_is_safe():
    state = _state_with_opportunities([_opportunity()])
    payload = get_institutional_investment_committee_payload(lambda: state)

    assert payload["advisory_only"] is True
    assert payload["live_trading_blocked"] is True
    assert payload["broker_execution_armed"] is False


def test_phase166_edge_cases_empty_and_invalid_inputs():
    empty = InstitutionalInvestmentCommittee().evaluate([], portfolio_context=_context())

    assert empty["decision"] == "WAIT"
    assert empty["evaluations"] == []
    with pytest.raises(ValueError):
        InstitutionalInvestmentCommittee().evaluate([object()], portfolio_context=_context())


def test_phase166_web_dashboard_contains_iic_panel():
    html = _dashboard_page()

    assert "Institutional Investment Committee" in html
    assert "committee-opportunity-list" in html
    assert "/api/v1/institutional-investment-committee" in str(create_app().routes)


def test_phase166_no_execution_authority_from_live_shaped_candidate():
    report = InstitutionalInvestmentCommittee().evaluate(
        [_opportunity(live_trading_enabled=True, can_live_execute=True)],
        portfolio_context=_context(),
    )

    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False
