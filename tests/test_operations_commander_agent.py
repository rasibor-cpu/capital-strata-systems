import pytest
from backend.app.ai_governance.operations_commander_agent import OperationsCommanderAgent

def test_missing_metadata_fails_closed():
    agent = OperationsCommanderAgent()
    result = agent.interpret_telemetry(None)
    assert result.status == "FAIL_CLOSED"
    assert result.incidents[0].description == "Missing telemetry metadata entirely."

def test_malformed_metadata_fails_closed():
    agent = OperationsCommanderAgent()
    result = agent.interpret_telemetry({"telemetry": "not a list"})
    assert result.status == "FAIL_CLOSED"
    assert result.incidents[0].description == "Malformed metadata: 'telemetry' must be a list."

def test_incident_classification_and_escalation():
    agent = OperationsCommanderAgent()
    metadata = {
        "telemetry": [
            {"type": "MARGIN_BREACH", "level": "P0", "description": "Margin limit exceeded", "runbook_mappings": ["MARGIN_RUNBOOK"]},
            {"type": "LATENCY_SPIKE", "level": "WARNING", "description": "High API latency"}
        ]
    }
    result = agent.interpret_telemetry(metadata)
    assert result.status == "INCIDENT"
    assert len(result.incidents) == 2
    
    p0_incident = [i for i in result.incidents if i.severity == "P0"][0]
    assert p0_incident.escalation_level == "L3"
    assert "MARGIN_RUNBOOK" in p0_incident.runbook_references

    warning_incident = [i for i in result.incidents if i.severity == "WARNING"][0]
    assert warning_incident.escalation_level == "L1"

def test_valid_ok_telemetry():
    agent = OperationsCommanderAgent()
    metadata = {
        "telemetry": [
            {"type": "HEARTBEAT", "level": "INFO"}
        ]
    }
    result = agent.interpret_telemetry(metadata)
    assert result.status == "OK"
    assert len(result.incidents) == 0

def test_agent_has_no_execution_side_effects():
    agent = OperationsCommanderAgent()
    assert not hasattr(agent, "execute_trade")
    assert not hasattr(agent, "modify_margin")
