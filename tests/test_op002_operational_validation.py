from __future__ import annotations

from datetime import datetime, timezone

from backend.runtime.broker_readiness_consolidation import build_canonical_broker_readiness
from backend.runtime.canonical_runtime_snapshot import build_canonical_runtime_snapshot
from backend.runtime.operational_validation_framework import build_operational_validation_report
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.runtime_snapshot_normalizer import normalize_runtime_snapshot
from dashboard.runtime.frontend_contract import broker as build_frontend_broker_section


def _frontend_payload() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    canonical_broker = {
        "broker": "COINBASE",
        "mode": "live_read_only",
        "credential_status": "PASS",
        "transport_status": "PASS",
        "authentication_status": "PASS",
        "connection_status": "PASS",
        "account_status": "PASS",
        "balance_status": "PASS",
        "buying_power_status": "PASS",
        "margin_status": "PASS",
        "market_data_status": "PASS",
        "product_status": "PASS",
        "readiness_score": 96.0,
        "overall_status": "GREEN",
        "state_hash": "broker-hash",
        "status_provenance": {"source": "test"},
        "warning_reasons": [],
        "source_modules": ["backend.runtime.canonical_broker_runtime_state"],
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    return {
        "payload_schema": "css.frontend.contract.v1",
        "generated_at": now,
        "mission_control_data_source": "RUNTIME",
        "source_metadata": {"source": "test"},
        "session": {"session_id": "op002", "cycle_number": 7, "engine_mode": "SAFE"},
        "sections": {
            "account_summary": {
                "cash_balance": 10000.0,
                "total_equity": 10100.0,
                "buying_power": 5000.0,
                "available_margin": 5000.0,
            },
            "positions": {"items": [], "total": 0, "total_exposure": 0.0, "by_asset": {}},
            "pnl_summary": {"realized_pnl": 100.0, "unrealized_pnl": 0.0, "net_pnl": 100.0, "total_exposure": 0.0},
            "risk": {"risk_state": "GREEN", "risk_score": 98.0, "gate_status": "PASS", "current_drawdown": 0.0, "total_exposure": 0.0},
            "market": {"regime_state": "RISK_ON"},
            "broker": {
                "selected_broker": "COINBASE",
                "broker_mode": "live_read_only",
                "broker_health": "GREEN",
                "last_heartbeat": now,
                "canonical_broker_runtime_state": canonical_broker,
                "runtime_certification_snapshot": {
                    "broker": "COINBASE",
                    "certification": "GREEN",
                    "operational_state": "GREEN",
                    "market_data_freshness": {"status": "GREEN"},
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                    "advisory_only": True,
                },
            },
            "runtime_certification_snapshot": {
                "broker": "COINBASE",
                "certification": "GREEN",
                "operational_state": "GREEN",
                "broker_readiness": "GREEN",
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            },
            "options_income": {
                "status": "PAPER_READY",
                "certification": "PAPER_CERTIFIED",
                "operational_readiness": "READY_FOR_PAPER_RUNTIME",
            },
            "institutional_investment_committee": {"status": "AVAILABLE"},
        },
    }


def test_op002_mission_control_uses_backend_canonical_runtime_snapshot() -> None:
    frontend = _frontend_payload()
    direct = build_canonical_runtime_snapshot(frontend)
    wrapped = normalize_runtime_snapshot(frontend)
    state = build_mission_control_state(frontend, allow_mock=False)

    assert wrapped["schema_version"] == "css.op002.canonical_runtime_snapshot.v1"
    assert direct["provenance"]["canonical_owner"] == "backend.runtime.canonical_runtime_snapshot"
    assert wrapped["provenance"]["canonical_owner"] == "backend.runtime.canonical_runtime_snapshot"
    assert state["runtime_snapshot"]["provenance"]["canonical_owner"] == "backend.runtime.canonical_runtime_snapshot"
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False


def test_op002_frontend_broker_section_exposes_canonical_readiness() -> None:
    frontend = _frontend_payload()
    broker_payload = build_frontend_broker_section({"broker_summary": frontend["sections"]["broker"]})

    readiness = broker_payload["canonical_broker_readiness"]
    assert broker_payload["broker_readiness"] == readiness
    assert readiness["schema_version"] == "css.op002.canonical_broker_readiness.v1"
    assert readiness["overall_status"] == "GREEN"
    assert readiness["ready_for_execution"] is False
    assert readiness["execution_allowed"] is False


def test_op002_operational_validation_passes_with_consistent_canonical_state() -> None:
    frontend = _frontend_payload()
    state = build_mission_control_state(frontend, allow_mock=False)

    report = build_operational_validation_report(frontend_payload=frontend, mission_control_state=state)

    assert report["summary"]["status"] == "PASS"
    assert report["checks"]["mission_control_hash"]["status"] == "PASS"
    assert report["checks"]["options_income"]["status"] == "PASS"
    assert report["checks"]["portfolio_risk_capital"]["status"] == "PASS"
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False
    assert report["advisory_only"] is True


def test_op002_operational_validation_fails_closed_on_hash_divergence() -> None:
    frontend = _frontend_payload()
    state = build_mission_control_state(frontend, allow_mock=False)
    state["runtime_snapshot"] = dict(state["runtime_snapshot"], state_hash="different")

    report = build_operational_validation_report(frontend_payload=frontend, mission_control_state=state)

    assert report["summary"]["status"] == "FAIL_CLOSED"
    assert "mission_control_hash" in report["summary"]["blockers"]
    assert report["execution_allowed"] is False


def test_op002_broker_readiness_fails_closed_for_missing_canonical_state() -> None:
    readiness = build_canonical_broker_readiness(broker_section={}, runtime_snapshot={}, certification_snapshot={})

    assert readiness["overall_status"] == "UNAVAILABLE"
    assert readiness["ready_for_read_only_validation"] is False
    assert readiness["ready_for_execution"] is False
    assert readiness["live_trading_blocked"] is True
