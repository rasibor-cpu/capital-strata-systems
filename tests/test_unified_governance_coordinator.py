import pytest
from backend.app.ai_governance.unified_governance_coordinator import UnifiedGovernanceCoordinator, ConsolidatedFinding
from backend.app.ai_governance.governance_auditor_agent import AuditResult, AuditFinding
from backend.app.ai_governance.certification_agent import ReadinessSummary, CertificationFinding
from backend.app.ai_governance.repository_intelligence_agent import RoadmapSummary, RoadmapFinding
from backend.app.ai_governance.operations_commander_agent import OperationsResult, IncidentSummary

def test_missing_or_invalid_inputs_fail_closed():
    coord = UnifiedGovernanceCoordinator()
    res = coord.aggregate_governance_state(None, None, None, None)
    assert res.governance_status == "FAIL_CLOSED"
    assert res.readiness_score == 0
    assert "Invalid or missing AuditResult" in res.critical_findings[0].issue

def test_valid_ready_state():
    coord = UnifiedGovernanceCoordinator()
    audit = AuditResult(status="VALID", findings=[])
    cert = ReadinessSummary(status="READY", findings=[])
    intell = RoadmapSummary(status="VALID", findings=[], completed_items=[], open_items=[])
    ops = OperationsResult(status="OK", incidents=[])
    
    res = coord.aggregate_governance_state(audit, cert, intell, ops)
    assert res.governance_status == "READY"
    assert res.readiness_score == 100
    assert not res.critical_findings
    assert not res.high_findings
    assert "System is ready." in res.recommended_actions[0]

def test_aggregation_and_severity_scoring():
    coord = UnifiedGovernanceCoordinator()
    audit = AuditResult(status="FINDINGS", findings=[AuditFinding(severity="HIGH", issue="Drift", component="None")])
    cert = ReadinessSummary(status="READY", findings=[])
    intell = RoadmapSummary(status="VALID", findings=[], completed_items=[], open_items=[])
    ops = OperationsResult(status="INCIDENT", incidents=[IncidentSummary(severity="WARNING", description="Lag", escalation_level="L1", runbook_references=[])])
    
    res = coord.aggregate_governance_state(audit, cert, intell, ops)
    assert res.governance_status == "NOT_READY"
    assert len(res.high_findings) == 1
    assert len(res.medium_findings) == 1
    # Score 100 - 25 (HIGH) - 10 (MEDIUM) = 65
    assert res.readiness_score == 65

def test_critical_forces_fail_closed():
    coord = UnifiedGovernanceCoordinator()
    audit = AuditResult(status="VALID", findings=[])
    cert = ReadinessSummary(status="FAIL_CLOSED", findings=[CertificationFinding(severity="CRITICAL", issue="Missing", reference_id="None")])
    intell = RoadmapSummary(status="VALID", findings=[], completed_items=[], open_items=[])
    ops = OperationsResult(status="OK", incidents=[])
    
    res = coord.aggregate_governance_state(audit, cert, intell, ops)
    assert res.governance_status == "FAIL_CLOSED"
    assert res.readiness_score == 0

def test_coordinator_has_no_execution_side_effects():
    coord = UnifiedGovernanceCoordinator()
    assert not hasattr(coord, "execute_trade")
    assert not hasattr(coord, "modify_margin")
