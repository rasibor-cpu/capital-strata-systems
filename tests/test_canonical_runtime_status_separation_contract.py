from __future__ import annotations

from datetime import datetime, timezone

from backend.runtime.canonical_runtime_snapshot import build_canonical_runtime_snapshot


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_red_certification_does_not_make_healthy_canonical_runtime_red():
    frontend = {
        "generated_at": _now(),
        "resolved_mode": "paper",
        "canonical_runtime_supervisor": {
            "status": "RUNNING",
            "last_heartbeat_at": _now(),
        },
        "sections": {
            "runtime_certification_snapshot": {
                "certification": "RED",
                "operational_state": "RED",
                "blocker_reasons": ["broker_evidence_missing"],
            },
            "broker": {
                "selected_broker": "QUESTRADE",
                "broker_health": "RED",
            },
            "account_summary": {},
            "pnl_summary": {},
            "positions": {},
            "risk": {},
            "market": {},
        },
    }

    snapshot = build_canonical_runtime_snapshot({}, frontend, source_name="test")

    assert snapshot["runtime_status"] == "ONLINE"
    assert snapshot["heartbeat_status"] == "FRESH"
    assert snapshot["runtime_health"] == "RED"
    assert snapshot["certification"]["runtime_readiness"] == "RED"
    assert snapshot["certification"]["blockers"] == ["broker_evidence_missing"]
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True
    assert snapshot["broker_execution_armed"] is False


def test_stale_heartbeat_still_fails_runtime_availability_closed():
    stale = "2020-01-01T00:00:00+00:00"
    frontend = {
        "generated_at": _now(),
        "resolved_mode": "paper",
        "sections": {
            "runtime_certification_snapshot": {
                "certification": "GREEN",
                "operational_state": "GREEN",
            },
            "broker": {},
            "account_summary": {},
            "pnl_summary": {},
            "positions": {},
            "risk": {},
            "market": {},
        },
    }

    # With no canonical supervisor, the stale broker heartbeat is the only
    # heartbeat evidence and runtime availability must remain stale/offline.
    frontend["sections"]["broker"]["last_heartbeat"] = stale

    snapshot = build_canonical_runtime_snapshot({}, frontend, source_name="test")

    assert snapshot["runtime_status"] in {"STALE", "OFFLINE"}
    assert snapshot["execution_allowed"] is False
