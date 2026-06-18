import pytest
from backend.app.ai_governance.governance_auditor_agent import GovernanceAuditorAgent

def test_missing_metadata_fails_closed():
    agent = GovernanceAuditorAgent()
    result = agent.audit_metadata(None)
    assert result.status == "FAIL_CLOSED"
    assert len(result.findings) == 1
    assert result.findings[0].issue == "Missing governance metadata entirely."

def test_missing_authority_register_fails_closed():
    agent = GovernanceAuditorAgent()
    result = agent.audit_metadata({"declarations": []})
    assert result.status == "FAIL_CLOSED"
    assert len(result.findings) == 1
    assert result.findings[0].issue == "Missing authority register in metadata."

def test_duplicate_authority_declarations_are_flagged():
    agent = GovernanceAuditorAgent()
    metadata = {
        "authority_register": True,
        "declarations": ["pnl_authority", "risk_authority", "pnl_authority"]
    }
    result = agent.audit_metadata(metadata)
    assert result.status == "FINDINGS"
    assert len(result.findings) == 1
    assert result.findings[0].issue == "Duplicate authority declaration detected: pnl_authority"
    assert result.findings[0].severity == "HIGH"

def test_incomplete_certification_references_are_flagged():
    agent = GovernanceAuditorAgent()
    metadata = {
        "authority_register": True,
        "certifications": [
            {"reference_id": "CERT-001", "status": "APPROVED"},
            {"status": "PENDING"}  # Missing reference_id
        ]
    }
    result = agent.audit_metadata(metadata)
    assert result.status == "FINDINGS"
    assert len(result.findings) == 1
    assert result.findings[0].issue == "Incomplete certification reference: {'status': 'PENDING'}"
    assert result.findings[0].severity == "MEDIUM"

def test_valid_governance_metadata_passes():
    agent = GovernanceAuditorAgent()
    metadata = {
        "authority_register": True,
        "declarations": ["pnl_authority", "risk_authority"],
        "certifications": [
            {"reference_id": "CERT-001", "status": "APPROVED"}
        ]
    }
    result = agent.audit_metadata(metadata)
    assert result.status == "PASS"
    assert len(result.findings) == 0

def test_agent_has_no_execution_side_effects():
    agent = GovernanceAuditorAgent()
    # The agent class purely contains memory-bound static analysis functions.
    # It has no imports from the broker or engine directories.
    assert not hasattr(agent, "execute_trade")
    assert not hasattr(agent, "modify_margin")
