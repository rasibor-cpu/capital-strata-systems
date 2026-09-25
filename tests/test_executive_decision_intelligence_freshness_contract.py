from __future__ import annotations

from backend.executive_decision_intelligence.service import ExecutiveDecisionIntelligenceService


class _Engine:
    def generate(self, state=None):
        return {
            "schema_version": "test",
            "generated_at": "2026-09-25T12:00:00Z",
            "executive_state": "READY",
            "priorities": [{"code": "p1", "title": "legacy priority"}],
            "immediate_actions": [{"code": "a1", "title": "legacy action"}],
            "escalations": [{"code": "e1", "title": "legacy escalation"}],
            "risks": [{"code": "r1", "title": "legacy risk"}],
            "opportunities": [{"code": "o1", "title": "legacy opportunity"}],
            "recommendations": [{"code": "rec1", "title": "legacy recommendation"}],
            "resource_priorities": [{"code": "res1"}],
            "recommended_next_action": {"code": "next1"},
            "scorecard": {"status": "READY"},
            "confidence": {"overall_confidence": 0.9, "confidence_band": "HIGH"},
            "recommended_executive_focus": "legacy",
            "top_five_priorities": [],
            "top_risks": [],
            "top_opportunities": [],
            "upstream": {},
            "disclaimer": "advisory",
        }

    def degraded(self):
        return {"executive_state": "DEGRADED"}


def _stale_state():
    return {
        "platform": {"runtime_mode": "DISABLED"},
        "runtime": {"heartbeat_status": "STALE"},
        "data_freshness": {
            "overall_freshness": "STALE",
            "stale_mandatory_data": True,
        },
    }


def test_stale_evidence_gates_all_edi_surfaces():
    service = ExecutiveDecisionIntelligenceService(engine=_Engine())
    state = _stale_state()

    priorities = service.priorities(state)
    risks = service.risks(state)
    opportunities = service.opportunities(state)
    recommendations = service.recommendations(state)
    scorecard = service.scorecard(state)

    for payload in (priorities, risks, opportunities, recommendations, scorecard):
        assert payload["executive_state"] == "NOT_READY"
        assert payload["freshness_gate"] == "STALE_OR_UNAVAILABLE"
        assert payload["evidence_current"] is False
        assert payload["advisory_only"] is True
        assert payload["trading_impact"] is False

    assert priorities["priorities"][0]["code"] == "priority:withheld_stale_evidence"
    assert risks["risks"][0]["code"] == "risk:withheld_stale_evidence"
    assert opportunities["opportunities"] == []
    assert recommendations["recommendations"][0]["code"] == "recommendation:withheld_stale_evidence"
    assert recommendations["resource_priorities"] == []
    assert scorecard["scorecard"]["status"] == "NOT_READY"
    assert scorecard["confidence"]["overall_confidence"] == 0.0
    assert scorecard["confidence"]["confidence_band"] == "VERY_LOW"


def test_current_evidence_preserves_engine_payloads():
    service = ExecutiveDecisionIntelligenceService(engine=_Engine())
    state = {
        "platform": {"runtime_mode": "ADVISORY"},
        "runtime": {"heartbeat_status": "ACTIVE"},
        "data_freshness": {"overall_freshness": "CURRENT"},
    }

    priorities = service.priorities(state)
    risks = service.risks(state)
    opportunities = service.opportunities(state)
    recommendations = service.recommendations(state)
    scorecard = service.scorecard(state)

    assert priorities["priorities"][0]["code"] == "p1"
    assert risks["risks"][0]["code"] == "r1"
    assert opportunities["opportunities"][0]["code"] == "o1"
    assert recommendations["recommendations"][0]["code"] == "rec1"
    assert scorecard["scorecard"]["status"] == "READY"
    assert scorecard["freshness_gate"] == "CURRENT"
    assert scorecard["evidence_current"] is True
