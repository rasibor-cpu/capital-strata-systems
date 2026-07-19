"""
Phase 176J — Executive Brief Readiness Orchestrator (reporting layer) tests.

Advisory / read-only: no broker, runtime, execution, or scheduler mutations.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.reporting.executive_brief_readiness_orchestrator import (
    STATE_AMBER,
    STATE_GREEN,
    STATE_NOT_READY,
    STATE_RED,
    ExecutiveBriefReadinessOrchestrator,
    ExecutiveBriefReadinessReport,
    evidence_from_mission_control_state,
)
from dashboard.runtime.api.executive_brief_readiness import (
    create_executive_brief_readiness_router,
)


def _full_ready_evidence() -> dict:
    return {
        "runtime": {"status": "HEALTHY"},
        "broker_connectivity": {"status": "GREEN"},
        "portfolio_snapshot": {"equity": 100000, "cash": 25000},
        "risk_metrics": {"status": "NORMAL", "overall_risk_state": "NORMAL"},
        "pnl": {"realized_pnl": 100.0, "unrealized_pnl": -20.0, "net_pnl": 80.0},
        "income_statement": {"net_income": 5000},
        "balance_sheet": {"assets": 100000, "liabilities": 10000, "equity": 90000},
        "cash_flow": {"operating": 1200},
        "market_intelligence": {"status": "READY", "market_regime": "RISK_ON"},
        "ai_recommendation_summary": {"status": "READY", "summary": "Hold"},
        "open_alerts": {"count": 0},
        "system_health": {"status": "HEALTHY"},
        "reporting_data_freshness": {"status": "FRESH", "age_seconds": 30},
    }


def test_readiness_calculation_green():
    orch = ExecutiveBriefReadinessOrchestrator()
    report = orch.generate_report(evidence=_full_ready_evidence())
    assert report.overall_state == STATE_GREEN
    assert report.score >= 85.0
    assert report.blocking_items == []
    assert report.advisory_only is True
    assert report.trading_impact is False


def test_blocking_detection_not_ready():
    evidence = _full_ready_evidence()
    del evidence["runtime"]
    del evidence["broker_connectivity"]
    orch = ExecutiveBriefReadinessOrchestrator()
    report = orch.generate_report(evidence=evidence)
    assert report.overall_state == STATE_NOT_READY
    assert report.blocking_items
    assert any("Runtime" in item for item in report.blocking_items)
    assert "Runtime" in report.missing_datasets
    assert "Broker Connectivity" in report.missing_datasets


def test_warning_detection_amber():
    evidence = _full_ready_evidence()
    evidence["risk_metrics"] = {"status": "WARNING"}
    evidence["open_alerts"] = {"count": 2}
    evidence["market_intelligence"] = {"status": "DEGRADED"}
    orch = ExecutiveBriefReadinessOrchestrator()
    report = orch.generate_report(evidence=evidence)
    assert report.warning_items
    # Non-critical warnings must not remain GREEN.
    assert report.overall_state == STATE_AMBER
    assert report.score <= 84.9
    assert any("Risk" in w or "alert" in w.lower() or "Market" in w for w in report.warning_items)


def test_outdated_datasets_and_red_path():
    evidence = _full_ready_evidence()
    evidence["reporting_data_freshness"] = {"age_seconds": 10_000}
    orch = ExecutiveBriefReadinessOrchestrator(
        freshness_soft_seconds=60,
        freshness_hard_seconds=120,
    )
    report = orch.generate_report(evidence=evidence)
    assert "Reporting Data Freshness" in report.outdated_datasets
    assert report.overall_state == STATE_RED
    assert report.score <= 69.0
    assert report.blocking_items


def test_score_generation_bounds():
    orch = ExecutiveBriefReadinessOrchestrator()
    empty = orch.generate_report(evidence={})
    assert 0.0 <= empty.score <= 100.0
    assert empty.overall_state == STATE_NOT_READY

    full = orch.generate_report(evidence=_full_ready_evidence())
    assert full.score > empty.score
    assert 0.0 <= full.score <= 100.0


def test_get_readiness_and_to_dict_serialization():
    orch = ExecutiveBriefReadinessOrchestrator()
    readiness = orch.get_readiness(evidence=_full_ready_evidence())
    assert readiness["overall_state"] == STATE_GREEN
    assert "overall_readiness_score" in readiness
    assert readiness["advisory_only"] is True
    assert readiness["trading_impact"] is False

    report = orch.generate_report(evidence=_full_ready_evidence())
    assert isinstance(report, ExecutiveBriefReadinessReport)
    payload = report.to_dict()
    assert payload["schema_version"].startswith("css.executive_brief_readiness_report")
    assert payload["overall_state"] == STATE_GREEN
    assert payload["score"] == report.score
    assert "blocking_items" in payload
    assert "warning_items" in payload
    assert "advisories" in payload
    assert "recommended_actions" in payload
    assert "estimated_generation_time" in payload
    assert isinstance(payload["components"], list)
    assert len(payload["components"]) >= 13

    via_orch = orch.to_dict(evidence=_full_ready_evidence())
    assert via_orch["overall_state"] == payload["overall_state"]


def test_advisory_financial_statements_missing():
    evidence = _full_ready_evidence()
    del evidence["income_statement"]
    del evidence["balance_sheet"]
    del evidence["cash_flow"]
    orch = ExecutiveBriefReadinessOrchestrator()
    report = orch.generate_report(evidence=evidence)
    assert report.advisories
    assert any("Income Statement" in a for a in report.advisories)
    # Blocking core still ready → should not be NOT_READY solely for advisories.
    assert report.overall_state in {STATE_GREEN, STATE_AMBER}


def test_evidence_from_mission_control_state():
    state = {
        "platform": {"runtime_health": "HEALTHY", "broker_health": "GREEN", "platform_status": "OK"},
        "runtime": {"heartbeat_status": "HEALTHY"},
        "portfolio": {
            "equity": 1,
            "realized_pnl": 1.0,
            "unrealized_pnl": 0.0,
            "net_pnl": 1.0,
        },
        "risk": {"status": "NORMAL"},
        "market_intelligence": {"status": "READY"},
        "alerts": {"count": 0},
        "data_freshness": {"overall_freshness": "FRESH", "age_seconds": 10},
        "brokers": {"status": "GREEN"},
        "institutional_reporting": {
            "income_statement": {"net_income": 1},
            "balance_sheet": {"assets": 1},
            "cash_flow": {"operating": 1},
        },
        "ai_recommendation_summary": {"status": "READY"},
    }
    evidence = evidence_from_mission_control_state(state)
    orch = ExecutiveBriefReadinessOrchestrator()
    report = orch.generate_report(evidence=evidence)
    assert report.score > 50
    assert report.overall_state in {STATE_GREEN, STATE_AMBER}


def test_api_response():
    app = FastAPI()
    app.include_router(
        create_executive_brief_readiness_router(
            state_provider=lambda: {
                "executive_brief_readiness_evidence": _full_ready_evidence(),
            }
        )
    )
    client = TestClient(app)
    res = client.get("/api/executive-brief/readiness")
    assert res.status_code == 200
    body = res.json()
    assert body["overall_state"] == STATE_GREEN
    assert body["advisory_only"] is True
    assert body["trading_impact"] is False
    assert "score" in body
    assert "blocking_items" in body
    assert "estimated_generation_time" in body
    assert "get_readiness" in body


def test_api_empty_provider_fail_closed():
    app = FastAPI()
    app.include_router(create_executive_brief_readiness_router(state_provider=None))
    client = TestClient(app)
    res = client.get("/api/executive-brief/readiness")
    assert res.status_code == 200
    body = res.json()
    assert body["overall_state"] == STATE_NOT_READY
    assert body["advisory_only"] is True


def test_estimated_generation_time_increases_with_gaps():
    orch = ExecutiveBriefReadinessOrchestrator()
    full = orch.generate_report(evidence=_full_ready_evidence())
    empty = orch.generate_report(evidence={})
    assert empty.estimated_generation_seconds > full.estimated_generation_seconds
    assert full.estimated_generation_time.startswith("~")


def test_exactly_thirteen_components():
    from backend.reporting.executive_brief_readiness_orchestrator import COMPONENT_SPECS

    assert len(COMPONENT_SPECS) == 13
    labels = [c.label for c in COMPONENT_SPECS]
    assert labels == [
        "Runtime",
        "Broker Connectivity",
        "Portfolio Snapshot",
        "Risk Metrics",
        "PnL",
        "Income Statement",
        "Balance Sheet",
        "Cash Flow",
        "Market Intelligence",
        "AI Recommendation Summary",
        "Open Alerts",
        "System Health",
        "Reporting Data Freshness",
    ]
    report = ExecutiveBriefReadinessOrchestrator().generate_report(evidence=_full_ready_evidence())
    assert len(report.components) == 13
    for comp in report.components:
        payload = comp.to_dict()
        assert "freshness_timestamp" in payload
        assert "classification" in payload
        assert "recommended_action" in payload
        assert "source_available" in payload


def test_not_ready_score_cannot_stay_high():
    evidence = _full_ready_evidence()
    del evidence["runtime"]
    del evidence["portfolio_snapshot"]
    report = ExecutiveBriefReadinessOrchestrator().generate_report(evidence=evidence)
    assert report.overall_state == STATE_NOT_READY
    assert report.score <= 49.0


def test_malformed_evidence_no_exception():
    orch = ExecutiveBriefReadinessOrchestrator()
    report = orch.generate_report(
        evidence={
            "runtime": "not-a-mapping",
            "broker_connectivity": 123,
            "portfolio_snapshot": [],
            "risk_metrics": None,
            "pnl": {"garbage": True},
            "open_alerts": {"count": "nope"},
            "reporting_data_freshness": {"age_seconds": "old"},
        }
    )
    assert report.overall_state in {STATE_NOT_READY, STATE_RED, STATE_AMBER, STATE_GREEN}
    assert 0.0 <= report.score <= 100.0
    assert report.recommended_actions


def test_provider_exception_isolation_in_component():
    class Boom(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("provider boom")

        def __contains__(self, key):
            return True

    evidence = _full_ready_evidence()
    evidence["runtime"] = Boom()
    report = ExecutiveBriefReadinessOrchestrator().generate_report(evidence=evidence)
    runtime = next(c for c in report.components if c.key == "runtime")
    assert runtime.status == "unavailable"
    assert report.overall_state == STATE_NOT_READY
    # Other components still evaluated.
    assert len(report.components) == 13


def test_evidence_not_mutated():
    evidence = _full_ready_evidence()
    evidence["runtime"] = {"status": "HEALTHY", "nested": {"x": 1}}
    snapshot = {
        "runtime": dict(evidence["runtime"]),
        "nested_x": evidence["runtime"]["nested"]["x"],
    }
    ExecutiveBriefReadinessOrchestrator().generate_report(evidence=evidence)
    assert evidence["runtime"]["status"] == snapshot["runtime"]["status"]
    assert evidence["runtime"]["nested"]["x"] == snapshot["nested_x"]


def test_deterministic_ordering_and_no_duplicate_lists():
    evidence = {}
    r1 = ExecutiveBriefReadinessOrchestrator().generate_report(evidence=evidence)
    r2 = ExecutiveBriefReadinessOrchestrator().generate_report(evidence=evidence)
    assert [c.key for c in r1.components] == [c.key for c in r2.components]
    assert r1.missing_datasets == r2.missing_datasets
    assert len(r1.missing_datasets) == len(set(r1.missing_datasets))
    assert len(r1.outdated_datasets) == len(set(r1.outdated_datasets))
    assert len(r1.blocking_items) == len(set(r1.blocking_items))
    # Missing and outdated are exclusive per component label.
    assert not (set(r1.missing_datasets) & set(r1.outdated_datasets))


def test_utc_timestamp_timezone_aware():
    report = ExecutiveBriefReadinessOrchestrator().generate_report(evidence=_full_ready_evidence())
    assert report.timestamp.endswith("Z")
    assert "T" in report.timestamp


def test_api_schema_repeatability_and_secrets_excluded():
    calls = {"n": 0}

    def provider():
        calls["n"] += 1
        return {"executive_brief_readiness_evidence": _full_ready_evidence()}

    app = FastAPI()
    app.include_router(create_executive_brief_readiness_router(state_provider=provider))
    client = TestClient(app)
    a = client.get("/api/executive-brief/readiness")
    b = client.get("/api/executive-brief/readiness")
    assert a.status_code == 200 and b.status_code == 200
    assert calls["n"] == 2
    body = a.json()
    required = {
        "timestamp",
        "overall_state",
        "score",
        "overall_readiness_score",
        "blocking_items",
        "warning_items",
        "advisories",
        "missing_datasets",
        "outdated_datasets",
        "recommended_actions",
        "estimated_generation_time",
        "components",
    }
    assert required <= set(body.keys())
    assert body["overall_state"] == b.json()["overall_state"]
    assert body["score"] == b.json()["score"]
    blob = str(body).lower()
    assert "traceback" not in blob
    assert "password" not in blob
    assert "api_key" not in body
    # JSON-serializable only
    import json

    json.dumps(body)


def test_api_provider_exception_still_200():
    def bad_provider():
        raise RuntimeError("upstream exploded")

    app = FastAPI()
    app.include_router(create_executive_brief_readiness_router(state_provider=bad_provider))
    client = TestClient(app)
    res = client.get("/api/executive-brief/readiness")
    assert res.status_code == 200
    body = res.json()
    assert body["overall_state"] == STATE_NOT_READY
    assert body["advisory_only"] is True
    assert "traceback" not in str(body).lower()


def test_executive_overview_card_not_ready_css_class():
    from dashboard.mission_control.pages.executive_overview import _readiness_state_class

    assert _readiness_state_class("GREEN") == "good"
    assert _readiness_state_class("AMBER") == "warn"
    assert _readiness_state_class("RED") == "bad"
    assert _readiness_state_class("NOT_READY") == "bad"
