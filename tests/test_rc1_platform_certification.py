from __future__ import annotations

import json
from backend.validation.rc1_platform_certifier import RC1PlatformCertifier


def _mock_payloads():
    portfolio = {
        "status": "OK",
        "portfolio_quality": 95.4,
        "expected_return": 12.5,
        "expected_drawdown": 4.5,
        "preferred_portfolio": [
            {"symbol": "SPY", "weight": 0.5},
            {"symbol": "TLT", "weight": 0.5},
        ],
        "ranked_opportunities": [
            {"symbol": "SPY", "expected_return": 18.0},
        ],
        "advisory_only": True,
        "execution_allowed": False,
    }
    optimizer = {
        "best_overall": "Balanced",
        "recommended_portfolios": [
            {"name": "Balanced", "quality_score": 95.4},
        ],
    }
    committee = {
        "status": "OK",
        "overall_recommendation": "APPROVE",
        "committee_vote": {
            "approve": 5,
            "conditional": 1,
            "reject": 0,
        },
        "advisory_only": True,
        "execution_allowed": False,
    }
    brief = {
        "overall_status": "GREEN",
        "market_regime": "Risk-On",
        "decision_confidence": 91.3,
        "broker_health": "GREEN",
        "runtime_health": "GREEN",
        "portfolio_quality": 95.4,
        "preferred_portfolio": "Balanced",
        "investment_committee": "APPROVE",
        "committee_vote": {
            "approve": 5,
            "conditional": 1,
            "reject": 0,
        },
        "execution_status": {
            "execution_authority": "NOT GRANTED",
            "live_trading": "BLOCKED",
            "broker_execution": "DISARMED",
        },
        "advisory_only": True,
        "execution_allowed": False,
    }
    dc = {
        "confidence": 91.3,
    }
    bh = {
        "health": "GREEN",
    }
    rh = {
        "status": "GREEN",
    }
    return portfolio, optimizer, committee, brief, dc, bh, rh


def test_rc1_platform_certification_clean_pass() -> None:
    certifier = RC1PlatformCertifier()
    pc, opt, comm, brief, dc, bh, rh = _mock_payloads()

    res = certifier.certify(
        portfolio_construction=pc,
        optimizer=opt,
        committee=comm,
        brief=brief,
        decision_confidence=dc,
        broker_health=bh,
        runtime_health=rh,
    )

    assert res["status"] == "PASS"
    assert res["overall_score"] >= 90.0
    assert res["release_recommendation"] == "Proceed to Operational Broker Certification"
    assert len(res["blockers"]) == 0
    assert len(res["warnings"]) == 0
    assert "RC1 PLATFORM CERTIFICATION SUMMARY" in res["console_report"]
    assert "# RC1 Platform Certification Report" in res["markdown_report"]

    parsed = json.loads(res["json_report"])
    assert parsed["evaluation"]["status"] == "PASS"


def test_rc1_platform_certification_warnings() -> None:
    certifier = RC1PlatformCertifier()
    pc, opt, comm, brief, dc, bh, rh = _mock_payloads()

    # Trigger a warning: low portfolio quality score
    pc["portfolio_quality"] = 45.0
    brief["portfolio_quality"] = 45.0

    res = certifier.certify(
        portfolio_construction=pc,
        optimizer=opt,
        committee=comm,
        brief=brief,
        decision_confidence=dc,
        broker_health=bh,
        runtime_health=rh,
    )

    assert res["status"] == "PASS WITH WARNINGS"
    assert res["release_recommendation"] == "Proceed to Long-Duration Validation"
    assert len(res["warnings"]) > 0


def test_rc1_platform_certification_fail_closed_on_safety_violation() -> None:
    certifier = RC1PlatformCertifier()
    pc, opt, comm, brief, dc, bh, rh = _mock_payloads()

    # Bypass safety gate: attempt to allow execution in one of the payload components
    pc["execution_allowed"] = True

    res = certifier.certify(
        portfolio_construction=pc,
        optimizer=opt,
        committee=comm,
        brief=brief,
        decision_confidence=dc,
        broker_health=bh,
        runtime_health=rh,
    )

    assert res["status"] == "FAIL"
    assert res["overall_score"] == 0.0
    assert res["release_recommendation"] == "Return to Engineering"
    assert any("Safety Gate Violated" in b for b in res["blockers"])


def test_rc1_platform_certification_fail_on_boundary_violation() -> None:
    certifier = RC1PlatformCertifier()
    pc, opt, comm, brief, dc, bh, rh = _mock_payloads()

    # Boundary violation: confidence score out of bounds
    dc["confidence"] = 150.0

    res = certifier.certify(
        portfolio_construction=pc,
        optimizer=opt,
        committee=comm,
        brief=brief,
        decision_confidence=dc,
        broker_health=bh,
        runtime_health=rh,
    )

    assert res["status"] == "FAIL"
    assert res["release_recommendation"] == "Return to Engineering"
    assert any("Boundary Violation" in b for b in res["blockers"])
