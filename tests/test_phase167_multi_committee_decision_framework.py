from __future__ import annotations

from fastapi.testclient import TestClient

from backend.investment_committee.committee_consensus import CommitteeConsensusEngine
from backend.investment_committee.committee_history import CommitteeHistoryStore
from backend.investment_committee.committee_models import CommitteeVote
from backend.investment_committee.investment_committee import InstitutionalInvestmentCommittee
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import build_frontend_payload


def _context(**overrides):
    data = {
        "available_capital": 100000.0,
        "deployable_capital": 50000.0,
        "equity": 125000.0,
        "max_approved_opportunities": 3,
        "max_expected_drawdown": 0.08,
        "max_risk_budget_consumption": 0.35,
        "max_sector_concentration": 0.40,
        "max_portfolio_correlation": 0.75,
        "min_committee_score": 60.0,
        "min_approval_score": 75.0,
        "min_low_priority_score": 65.0,
        "market_health": 0.86,
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
        "expected_return": 0.038,
        "probability_of_success": 0.84,
        "expected_drawdown": 0.025,
        "expected_holding_period": 3,
        "capital_efficiency": 0.94,
        "portfolio_correlation": 0.22,
        "sector_concentration": 0.12,
        "asset_allocation_impact": 0.82,
        "regime_suitability": 0.90,
        "liquidity": 0.92,
        "spread_quality": 0.88,
        "execution_cost": 0.04,
        "volatility": 0.24,
        "risk_budget_consumption": 0.14,
        "strategy_confidence": 0.86,
        "signal_quality": 0.88,
        "historical_similarity": 0.82,
        "decision_confidence": 0.88,
        "operational_readiness": 0.90,
        "market_health": 0.86,
        "momentum": 0.88,
        "runtime_health": 0.90,
        "market_data_freshness": 0.92,
        "operational_certification": 0.90,
    }
    data.update(overrides)
    return data


def _vote(name: str, vote: str, score: float = 80.0, veto: str = "") -> CommitteeVote:
    return CommitteeVote(
        committee=name,
        vote=vote,
        confidence=score / 100.0,
        committee_score=score,
        reason=f"{name} voted {vote}",
        veto=veto,
    )


def _state(opportunities):
    state = DashboardState()
    state.last_scan_results["opportunities"] = opportunities
    state.last_scan_results["account_summary"] = {
        "cash_balance": 100000.0,
        "buying_power": 100000.0,
        "total_equity": 125000.0,
        "broker": "DEMO",
    }
    state.last_scan_results["risk_summary"] = {"max_committee_approved_opportunities": 2}
    state.last_scan_results["position_state"] = {"positions": []}
    state.broker_state.selected_broker = "DEMO"
    state.broker_state.api_health = "GREEN"
    return state


def test_phase167_unanimous_approval():
    report = InstitutionalInvestmentCommittee().evaluate([_opportunity()], portfolio_context=_context())

    assert report["decision"] == "APPROVED"
    assert report["consensus_summary"]["consensus"] == "UNANIMOUS_APPROVAL"
    assert len(report["evaluations"][0]["committee_votes"]) == 6
    assert report["execution_allowed"] is False


def test_phase167_majority_approval():
    consensus = CommitteeConsensusEngine().aggregate(
        [
            _vote("Market", "APPROVE"),
            _vote("Risk", "APPROVE_WITH_CAUTION", 70),
            _vote("Capital", "APPROVE"),
            _vote("Portfolio", "WAIT", 55),
            _vote("Liquidity", "APPROVE_WITH_CAUTION", 68),
            _vote("Operational", "WAIT", 55),
        ]
    )

    assert consensus["institutional_recommendation"] == "APPROVED_LOW_PRIORITY"
    assert consensus["consensus"] == "MAJORITY_APPROVAL"


def test_phase167_split_vote_waits():
    consensus = CommitteeConsensusEngine().aggregate(
        [
            _vote("Market", "APPROVE"),
            _vote("Risk", "REJECT", 35),
            _vote("Capital", "APPROVE_WITH_CAUTION", 68),
            _vote("Portfolio", "REJECT", 35),
            _vote("Liquidity", "WAIT", 50),
            _vote("Operational", "WAIT", 55),
        ]
    )

    assert consensus["institutional_recommendation"] == "WAIT"
    assert consensus["consensus"] == "SPLIT_COMMITTEE"


def test_phase167_risk_veto():
    report = InstitutionalInvestmentCommittee().evaluate(
        [
            _opportunity(
                expected_drawdown=0.40,
                probability_of_success=0.20,
                risk_budget_consumption=0.90,
                stop_distance=0.90,
                regime_suitability=0.10,
            )
        ],
        portfolio_context=_context(),
    )

    assert report["decision"] == "RISK_VETO"
    assert "RISK_VETO" in report["consensus_summary"]["veto_reasons"]


def test_phase167_portfolio_veto():
    report = InstitutionalInvestmentCommittee().evaluate(
        [_opportunity(portfolio_correlation=0.99, sector_concentration=0.99, asset_allocation_impact=0.05)],
        portfolio_context=_context(),
    )

    assert report["decision"] == "PORTFOLIO_VETO"
    assert "PORTFOLIO_VETO" in report["consensus_summary"]["veto_reasons"]


def test_phase167_liquidity_veto():
    report = InstitutionalInvestmentCommittee().evaluate(
        [_opportunity(liquidity=0.05, spread_quality=0.05, execution_cost=0.95, slippage_risk=0.95)],
        portfolio_context=_context(),
    )

    assert report["decision"] == "LIQUIDITY_VETO"
    assert "LIQUIDITY_VETO" in report["consensus_summary"]["veto_reasons"]


def test_phase167_operational_veto():
    report = InstitutionalInvestmentCommittee().evaluate(
        [
            _opportunity(
                operational_readiness=0.0,
                runtime_health=0.0,
                broker_certification=0.0,
                operational_certification=0.0,
                market_data_freshness=0.0,
            )
        ],
        portfolio_context=_context(operational_readiness=0.0),
    )

    assert report["decision"] == "OPERATIONAL_VETO"
    assert "OPERATIONAL_VETO" in report["consensus_summary"]["veto_reasons"]


def test_phase167_capital_displacement():
    report = InstitutionalInvestmentCommittee().evaluate(
        [_opportunity("BTC-USD"), _opportunity("ETH-USD", expected_return=0.036)],
        portfolio_context=_context(max_approved_opportunities=1, deployable_capital=10000.0),
    )

    decisions = [item["decision"] for item in report["evaluations"]]
    assert "APPROVED" in decisions
    assert "CAPITAL_BETTER_DEPLOYED" in decisions


def test_phase167_history_serialization():
    store = CommitteeHistoryStore()
    item = store.record(
        opportunity_id="opp-1",
        votes=[_vote("Market", "APPROVE").as_dict()],
        recommendation="APPROVED",
        confidence=0.82,
        consensus={"consensus": "UNANIMOUS_APPROVAL"},
        explanations=["Market approved."],
    )

    assert item["timestamp"]
    assert item["recommendation"] == "APPROVED"
    assert item["votes"][0]["committee"] == "Market"
    assert store.records()[0]["execution_allowed"] is False


def test_phase167_dashboard_serialization():
    payload = build_frontend_payload(_state([_opportunity()]))
    section = payload["sections"]["institutional_investment_committee"]

    assert section["committee_votes"]
    assert section["consensus_score"] > 0
    assert section["committee_explanations"][0]["reason"]
    assert section["execution_allowed"] is False


def test_phase167_api_serialization():
    client = TestClient(create_app(lambda: _state([_opportunity()])))

    report_response = client.get("/api/v1/institutional-investment-committee")
    votes_response = client.get("/api/v1/institutional-investment-committee/votes")

    assert report_response.status_code == 200
    assert votes_response.status_code == 200
    assert report_response.json()["data"]["consensus_summary"]["consensus"] == "UNANIMOUS_APPROVAL"
    assert votes_response.json()["committee_votes"]
    assert votes_response.json()["execution_allowed"] is False


def test_phase167_edge_cases_no_votes_and_abstain():
    no_votes = CommitteeConsensusEngine().aggregate([])
    abstain = CommitteeConsensusEngine().aggregate([_vote("Market", "ABSTAIN", 0)])

    assert no_votes["institutional_recommendation"] == "WAIT"
    assert abstain["institutional_recommendation"] == "WAIT"
    assert no_votes["execution_allowed"] is False
