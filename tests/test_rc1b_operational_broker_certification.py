from __future__ import annotations

from backend.validation.operational_broker_certifier import OperationalBrokerCertifier


def _oanda_conn_mock(latency_status="AMBER"):
    return {
        "phase156a": "GREEN",
        "authentication": "PASS",
        "account": "PASS",
        "market_data": "PASS",
        "latency_status": latency_status,
        "execution_allowed": False,
        "advisory_only": True,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "stage_results": {
            "execution_firewall": {
                "status": "PASS",
                "details": {
                    "execution_boundary_active": True,
                }
            }
        }
    }


def test_rc1b_oanda_degraded_operational_readiness_is_go_read_only() -> None:
    certifier = OperationalBrokerCertifier()
    conn = _oanda_conn_mock(latency_status="AMBER")

    res = certifier.certify_broker("oanda", phase156b_connectivity=conn)

    assert res["report"]["overall_recommendation"] == "GO_READ_ONLY"
    assert res["report"]["overall_state"] == "AMBER"
    assert res["report"]["latency"] == "AMBER"
    assert res["report"]["health"] == "GREEN"
    assert res["report"]["overall_score"] >= 85.0

    # Assert safety gate constraints
    assert res["report"]["advisory_only"] is True
    assert res["report"]["execution_allowed"] is False
    assert res["report"]["live_trading_blocked"] is True
    assert res["report"]["broker_execution_armed"] is False


def test_rc1b_coinbase_successful_readiness_is_go() -> None:
    certifier = OperationalBrokerCertifier()
    conn = _oanda_conn_mock(latency_status="GREEN")

    res = certifier.certify_broker("coinbase", phase156b_connectivity=conn)

    assert res["report"]["overall_recommendation"] == "GO"
    assert res["report"]["overall_state"] == "GREEN"
    assert res["report"]["latency"] == "GREEN"
    assert res["report"]["overall_score"] == 100.0


def test_rc1b_fails_closed_on_safety_violation() -> None:
    certifier = OperationalBrokerCertifier()
    conn = _oanda_conn_mock(latency_status="GREEN")
    
    # Simulate a safety bypass trigger
    conn["execution_allowed"] = True

    res = certifier.certify_broker("oanda", phase156b_connectivity=conn)

    assert res["report"]["overall_recommendation"] == "NO_GO"
    assert res["report"]["overall_state"] == "RED"
    assert res["report"]["production_readiness"] == "NOT_READY"
    assert res["report"]["overall_score"] == 100.0  # Raw score remains, but state is overridden to RED
    assert "Safety Gate Violated: Advisory boundary bypass detected in inputs." in res["report"]["remaining_blockers"]


def test_rc1b_historical_computations() -> None:
    certifier = OperationalBrokerCertifier()
    conn = _oanda_conn_mock(latency_status="AMBER")
    
    history = {
        "overall_score": 90.0,
        "overall_state": "GREEN",
    }

    res = certifier.certify_broker("oanda", phase156b_connectivity=conn, previous_history=history)

    assert res["report"]["previous_score"] == 90.0
    assert res["report"]["score_delta"] == 2.5  # 92.5 - 90.0
    assert res["report"]["previous_state"] == "GREEN"
    assert res["report"]["state_changed"] is True
