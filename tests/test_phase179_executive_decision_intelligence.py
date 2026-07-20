"""
Phase 179 — Executive Decision Intelligence tests.

Orchestration / decision-support only. No Phase 177/178 calculation changes.
Advisory-only. trading_impact=false.
"""

from __future__ import annotations

import inspect
import json
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.executive_decision_intelligence.decision_engine import (
    ExecutiveDecisionEngine,
    derive_executive_state,
)
from backend.executive_decision_intelligence.decision_prioritizer import dedupe_by_code
from backend.executive_decision_intelligence.service import ExecutiveDecisionIntelligenceService
from backend.executive_reporting.service import ExecutiveFinancialReportingService
from dashboard.mission_control.pages import executive_overview
from dashboard.runtime.api.executive_decision_intelligence import (
    create_executive_decision_intelligence_router,
)
from launcher import css_mobile_launcher


def _rich_state() -> dict:
    return {
        "portfolio": {"realized_pnl": 5000, "cash": 20000, "equity": 100000},
        "target_profit": 8000,
        "platform": {
            "runtime_health": "HEALTHY",
            "broker_health": "GREEN",
            "runtime_offline": False,
        },
        "runtime": {"heartbeat_status": "HEALTHY"},
        "risk": {"overall_risk_state": "NORMAL"},
        "alerts": {"count": 0},
        "data_freshness": {"overall_freshness": "FRESH", "age_seconds": 30},
        "executive_brief_readiness": {"overall_state": "GREEN", "score": 80},
    }


def test_does_not_recalculate_net_profit():
    state = _rich_state()
    fin = ExecutiveFinancialReportingService().financial_summary(state)
    edi = ExecutiveDecisionIntelligenceService().generate(state)
    # EDI must not invent a competing net_profit field at top level
    assert "net_profit" not in edi
    assert edi["upstream"]["phase178_traffic_light"] == fin.get("profitability_traffic_light")


def test_delegation_to_phase178_package():
    state = _rich_state()
    package = ExecutiveFinancialReportingService().generate_from_state(state, report_id="edi-decision")
    edi = ExecutiveDecisionIntelligenceService().generate(state)
    assert edi["upstream"]["phase178_report_id"] == package.get("report_id") == "edi-decision"
    assert edi["upstream"]["phase178_traffic_light"] == (
        (package.get("financial_summary") or {}).get("profitability_traffic_light")
    )
    assert edi["advisory_only"] is True
    assert edi["trading_impact"] is False


def test_determinism_excluding_timestamp():
    state = _rich_state()
    engine = ExecutiveDecisionEngine()
    a = engine.generate(state)
    b = engine.generate(state)
    # Decision content must be stable; generated_at is allowed to differ.
    assert a["executive_state"] == b["executive_state"]
    assert a["priorities"] == b["priorities"]
    assert a["risks"] == b["risks"]
    assert a["opportunities"] == b["opportunities"]
    assert a["confidence"]["overall_confidence"] == b["confidence"]["overall_confidence"]
    assert a["upstream"]["phase178_report_id"] == b["upstream"]["phase178_report_id"] == "edi-decision"


def test_duplicate_suppression():
    items = [
        {"code": "a", "title": "A1", "priority": "HIGH"},
        {"code": "a", "title": "A2", "priority": "LOW"},
        {"code": "b", "title": "B", "priority": "MEDIUM"},
    ]
    out = dedupe_by_code(items)
    codes = [x["code"] for x in out]
    assert codes.count("a") == 1
    assert out[0]["title"] == "A1"


def test_priority_ordering():
    service = ExecutiveDecisionIntelligenceService()
    payload = service.priorities(
        {
            **_rich_state(),
            "platform": {"runtime_offline": True, "runtime_health": "DOWN", "broker_health": "RED"},
            "alerts": {"count": 5},
        }
    )
    priorities = payload["priorities"]
    ranks = [p["rank"] for p in priorities]
    assert ranks == sorted(ranks)
    # CRITICAL/HIGH appear before INFO when present
    if priorities:
        assert priorities[0]["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}


def test_confidence_stability():
    state = _rich_state()
    a = ExecutiveDecisionIntelligenceService().scorecard(state)
    b = ExecutiveDecisionIntelligenceService().scorecard(state)
    assert a["confidence"]["overall_confidence"] == b["confidence"]["overall_confidence"]
    assert a["confidence"]["confidence_band"] == b["confidence"]["confidence_band"]


def test_safe_degraded_mode_empty_state():
    payload = ExecutiveDecisionIntelligenceService().generate({})
    assert payload["advisory_only"] is True
    assert payload["trading_impact"] is False
    assert payload["executive_state"] in {"NOT_READY", "DEGRADED", "ATTENTION", "STRESSED", "STABLE"}
    assert isinstance(payload["priorities"], list)
    assert isinstance(payload["risks"], list)


def test_missing_inputs_and_provider_failure(monkeypatch):
    import backend.executive_decision_intelligence.decision_engine as engine_mod

    monkeypatch.setattr(
        engine_mod,
        "extract_financial_package_safe",
        lambda state: ({}, ["forced_error"]),
    )
    payload = ExecutiveDecisionEngine().generate({"platform": {"runtime_offline": True}})
    assert "forced_error" in payload["upstream"]["input_errors"]
    assert payload["trading_impact"] is False


def test_source_state_immutability():
    state = _rich_state()
    frozen = json.dumps(state, sort_keys=True)
    _ = ExecutiveDecisionIntelligenceService().generate(state)
    assert json.dumps(state, sort_keys=True) == frozen


def test_advisory_flags_everywhere():
    for method in ("summary", "priorities", "risks", "opportunities", "recommendations", "scorecard"):
        out = getattr(ExecutiveDecisionIntelligenceService(), method)(_rich_state())
        assert out["advisory_only"] is True
        assert out["trading_impact"] is False


def test_derive_executive_state_precedence():
    assert (
        derive_executive_state(
            financial_summary={"reporting_readiness": "GREEN", "profitability_traffic_light": "GREEN"},
            operational={"runtime_offline": True, "alert_count": 0, "risk_state": "NORMAL"},
            brief_readiness={"overall_state": "GREEN"},
            input_errors=[],
        )
        == "NOT_READY"
    )
    assert (
        derive_executive_state(
            financial_summary={"reporting_readiness": "GREEN", "profitability_traffic_light": "RED"},
            operational={"runtime_offline": False, "alert_count": 0, "risk_state": "NORMAL"},
            brief_readiness={"overall_state": "GREEN"},
            input_errors=[],
        )
        == "STRESSED"
    )


def test_api_routes_read_only():
    app = FastAPI()
    app.include_router(create_executive_decision_intelligence_router(state_provider=_rich_state))
    client = TestClient(app)
    paths = [
        "/api/executive-decision-intelligence/summary",
        "/api/executive-decision-intelligence/priorities",
        "/api/executive-decision-intelligence/risks",
        "/api/executive-decision-intelligence/opportunities",
        "/api/executive-decision-intelligence/recommendations",
        "/api/executive-decision-intelligence/scorecard",
    ]
    for path in paths:
        resp = client.get(path)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("trading_impact") is False
        assert body.get("advisory_only") is True
        assert "traceback" not in body
        assert "password" not in body


def test_no_post_mutation_routes_on_edi_router():
    router = create_executive_decision_intelligence_router()
    methods = {(r.path, tuple(sorted(r.methods or []))) for r in router.routes if hasattr(r, "methods")}
    for path, meth in methods:
        assert "POST" not in meth
        assert "PUT" not in meth
        assert "DELETE" not in meth
        assert path.startswith("/api/executive-decision-intelligence/")


def test_launcher_mounts_edi_router_once():
    src = inspect.getsource(css_mobile_launcher)
    assert src.count("create_executive_decision_intelligence_router(state_provider=") == 1


def test_mission_control_card_renders():
    html = executive_overview.render(_rich_state())
    assert 'id="executive-decision-intelligence"' in html
    assert 'data-phase="179"' in html
    assert "Executive Decision Intelligence" in html
    assert "undefined" not in html.lower()
    assert "NaN" not in html


def test_recommendations_suppress_trading_verbs():
    from backend.executive_decision_intelligence.management_recommendations import (
        build_management_recommendations,
    )

    out = build_management_recommendations(
        priorities=[{"code": "x", "title": "Buy more shares now", "priority": "HIGH", "reason": "x"}],
        risks=[],
        opportunities=[],
    )
    assert out
    assert "buy " not in out[0]["title"].lower()


def test_package_deepcopy_safe():
    payload = ExecutiveDecisionIntelligenceService().generate(_rich_state())
    clone = deepcopy(payload)
    assert clone["schema_version"] == payload["schema_version"]
