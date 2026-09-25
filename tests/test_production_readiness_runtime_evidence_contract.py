from __future__ import annotations

from dashboard.mission_control import contracts


def test_runtime_certification_evidence_projects_into_production_readiness(monkeypatch):
    runtime_snapshot = {
        "runtime_status": "ONLINE",
        "heartbeat_status": "FRESH",
        "runtime_health": "RED",
        "source": "RUNTIME",
        "state_hash": "runtime-hash",
        "certification": {
            "broker_readiness": "RED",
            "runtime_readiness": "RED",
            "blockers": ["phase156a_not_green"],
        },
        "broker": {
            "selected_broker": "COINBASE",
            "transport": "FAIL",
        },
    }

    monkeypatch.setattr(
        contracts,
        "_runtime_snapshot",
        lambda dashboard_state, frontend: dict(runtime_snapshot),
    )

    state = contracts.build_mission_control_state(
        {
            "frontend_payload": {
                "generated_at": "2026-09-25T12:00:00+00:00",
                "sections": {},
            }
        },
        allow_mock=True,
    )

    readiness = state["production_readiness"]
    assert readiness["status"] == "NOT_CERTIFIED"
    assert readiness["broker_readiness"] == "RED"
    assert readiness["runtime_readiness"] == "RED"
    assert "phase156a_not_green" in readiness["deployment_blockers"]
    assert "broker_connection_failed" in readiness["deployment_blockers"]
    assert readiness["certification_score"] == 0
    assert readiness["evidence_completeness"] == 0
    assert readiness["deployment_authorized"] is False
    assert readiness["production_trading_certified"] is False
    assert readiness["execution_allowed"] is False
