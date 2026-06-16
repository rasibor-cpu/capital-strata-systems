import pytest
from backend.app.ai_governance.repository_intelligence_agent import RepositoryIntelligenceAgent

def test_missing_metadata_fails_closed():
    agent = RepositoryIntelligenceAgent()
    result = agent.analyze_roadmap(None)
    assert result.status == "FAIL_CLOSED"
    assert result.findings[0].issue == "Missing repository metadata entirely."

def test_malformed_metadata_fails_closed():
    agent = RepositoryIntelligenceAgent()
    result = agent.analyze_roadmap({"other_key": []})
    assert result.status == "FAIL_CLOSED"
    assert result.findings[0].issue == "Malformed metadata: missing 'roadmap' key."

    result2 = agent.analyze_roadmap({"roadmap": "not a list"})
    assert result2.status == "FAIL_CLOSED"

def test_duplicate_roadmap_entries_flagged():
    agent = RepositoryIntelligenceAgent()
    metadata = {
        "roadmap": [
            {"id": "TASK-001", "status": "COMPLETED"},
            {"id": "TASK-001", "status": "OPEN"}
        ]
    }
    result = agent.analyze_roadmap(metadata)
    assert result.status == "FINDINGS"
    duplicate_findings = [f for f in result.findings if "Duplicate" in f.issue]
    assert len(duplicate_findings) == 1
    assert duplicate_findings[0].item_id == "TASK-001"

def test_completed_versus_open_items():
    agent = RepositoryIntelligenceAgent()
    metadata = {
        "roadmap": [
            {"id": "TASK-001", "status": "COMPLETED"},
            {"id": "TASK-002", "status": "OPEN"},
            {"id": "TASK-003", "status": "PENDING"}
        ]
    }
    result = agent.analyze_roadmap(metadata)
    assert result.status == "VALID"
    assert len(result.completed_items) == 1
    assert "TASK-001" in result.completed_items
    assert len(result.open_items) == 2
    assert "TASK-002" in result.open_items
    assert "TASK-003" in result.open_items

def test_authority_drift_risks_are_flagged():
    agent = RepositoryIntelligenceAgent()
    metadata = {
        "roadmap": [{"id": "TASK-001", "status": "COMPLETED"}],
        "authority_drift_risks": ["Unauthorized import in core engine"]
    }
    result = agent.analyze_roadmap(metadata)
    assert result.status == "FINDINGS"
    drift_findings = [f for f in result.findings if "drift risk flagged" in f.issue]
    assert len(drift_findings) == 1
    assert "Unauthorized import" in drift_findings[0].issue

def test_agent_has_no_execution_side_effects():
    agent = RepositoryIntelligenceAgent()
    assert not hasattr(agent, "execute_trade")
    assert not hasattr(agent, "modify_margin")
