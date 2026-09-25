from __future__ import annotations

from dashboard.mission_control.final_certification import build_final_certification


def _base_state() -> dict:
    return {
        "runtime": {
            "runtime_status": "RUNNING",
            "heartbeat_status": "FRESH",
            "source": "RUNTIME",
            "state_hash": "runtime-hash",
        },
        "brokers": {
            "active_broker": {
                "selected_broker": "QUESTRADE",
                "connection_status": "READ_ONLY_READY",
            }
        },
        "portfolio": {"equity": 1000},
        "decision_panel": {"status": "READY"},
        "operations_timeline": {"events": [{"event": "runtime"}]},
        "committee_view": {"status": "READY"},
        "governance_summary_console": {"status": "ready"},
        "safety": {
            "safety_status": "PASS",
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        },
        "rbac_console": {"status": "ready"},
        "source_consistency": {"status": "PASS"},
        "state_hash": "state-hash",
        "contract_validation": {"valid": True},
        "documentation": {
            "governance": ["docs/governance/MISSION_CONTROL_FINAL_CERTIFICATION.md"]
        },
        "production_readiness": {
            "status": "CERTIFIED",
            "broker_readiness": "CERTIFIED",
            "runtime_readiness": "CERTIFIED",
            "evidence_completeness": 100,
            "deployment_authorized": True,
            "production_trading_certified": True,
        },
    }


def test_final_certification_fails_closed_when_production_is_not_certified():
    state = _base_state()
    state["production_readiness"] = {
        "status": "NOT_CERTIFIED",
        "broker_readiness": "EVIDENCE_MISSING",
        "runtime_readiness": "EVIDENCE_MISSING",
        "evidence_completeness": 0,
        "deployment_authorized": False,
        "production_trading_certified": False,
    }

    result = build_final_certification(state)

    assert result["overall"] == "FAIL_CLOSED"
    assert "production_readiness" in result["blockers"]
    check = next(item for item in result["checks"] if item["area"] == "production_readiness")
    assert check["status"] == "FAIL_CLOSED"
    assert check["reason"] == "production_readiness_not_certified"


def test_final_certification_fails_closed_when_runtime_is_red_even_with_fresh_heartbeat():
    state = _base_state()
    state["runtime"]["runtime_status"] = "RED"
    state["runtime"]["heartbeat_status"] = "FRESH"

    result = build_final_certification(state)

    assert result["overall"] == "FAIL_CLOSED"
    assert "runtime" in result["blockers"]
    check = next(item for item in result["checks"] if item["area"] == "runtime")
    assert check["reason"] == "runtime_status_red"


def test_final_certification_can_certify_only_when_all_areas_are_ready():
    result = build_final_certification(_base_state())
    assert result["overall"] == "CERTIFIED"
    assert result["blockers"] == []
