import pytest
from backend.app.ai_governance.certification_agent import CertificationAgent

def test_missing_metadata_fails_closed():
    agent = CertificationAgent()
    result = agent.evaluate_readiness(None)
    assert result.status == "FAIL_CLOSED"
    assert result.findings[0].issue == "Missing certification metadata entirely."

def test_malformed_metadata_fails_closed():
    agent = CertificationAgent()
    result = agent.evaluate_readiness({"declarations": []})
    assert result.status == "FAIL_CLOSED"
    assert result.findings[0].issue == "Malformed metadata: missing 'certifications' key."

    result2 = agent.evaluate_readiness({"certifications": "not a list"})
    assert result2.status == "FAIL_CLOSED"

def test_missing_certifications_flagged():
    agent = CertificationAgent()
    metadata = {
        "certifications": [
            {"reference_id": "107A", "status": "APPROVED"}
            # Missing 107B through 108E
        ]
    }
    result = agent.evaluate_readiness(metadata)
    assert result.status == "NOT_READY"
    missing_107b = [f for f in result.findings if f.reference_id == "107B"]
    assert len(missing_107b) == 1
    assert "Missing required certification: 107B" in missing_107b[0].issue

def test_expired_certifications_flagged():
    agent = CertificationAgent()
    metadata = {
        "certifications": [{"reference_id": phase, "status": "APPROVED"} for phase in agent.required_phases]
    }
    metadata["certifications"][0]["status"] = "EXPIRED"

    result = agent.evaluate_readiness(metadata)
    assert result.status == "NOT_READY"
    assert result.findings[0].severity == "HIGH"
    assert "EXPIRED" in result.findings[0].issue

def test_incomplete_certification_chains_flagged():
    agent = CertificationAgent()
    metadata = {
        "certifications": [{"reference_id": phase, "status": "APPROVED"} for phase in agent.required_phases]
    }
    # Create a dependency that is not approved
    metadata["certifications"].append({"reference_id": "EXTRA_DEP", "status": "PENDING"})
    # Make 108E depend on it
    for cert in metadata["certifications"]:
        if cert["reference_id"] == "108E":
            cert["depends_on"] = ["EXTRA_DEP"]

    result = agent.evaluate_readiness(metadata)
    assert result.status == "NOT_READY"
    chain_finding = [f for f in result.findings if "depends on EXTRA_DEP" in f.issue]
    assert len(chain_finding) == 1
    assert chain_finding[0].severity == "HIGH"

def test_valid_certification_inventory_passes():
    agent = CertificationAgent()
    metadata = {
        "certifications": [{"reference_id": phase, "status": "APPROVED"} for phase in agent.required_phases]
    }
    result = agent.evaluate_readiness(metadata)
    assert result.status == "READY"
    assert len(result.findings) == 0

def test_agent_has_no_execution_side_effects():
    agent = CertificationAgent()
    # The agent purely parses dictionaries
    assert not hasattr(agent, "execute_trade")
    assert not hasattr(agent, "modify_margin")
