#!/usr/bin/env python3
import sys
import json
from backend.app.ai_governance.governance_auditor_agent import GovernanceAuditorAgent
from backend.app.ai_governance.certification_agent import CertificationAgent
from backend.app.ai_governance.repository_intelligence_agent import RepositoryIntelligenceAgent
from backend.app.ai_governance.operations_commander_agent import OperationsCommanderAgent
from backend.app.ai_governance.unified_governance_coordinator import UnifiedGovernanceCoordinator

def get_valid_audit_metadata():
    return {
        "authority_register": {"valid": True},
        "declarations": ["trade", "margin"],
        "certifications": [{"reference_id": "108", "status": "APPROVED"}]
    }

def get_valid_certification_metadata():
    return {
        "certifications": [
            {"reference_id": p, "status": "APPROVED"} 
            for p in ["107A", "107B", "107C", "107D", "107E", "107F", "108A", "108B", "108C", "108D", "108E"]
        ]
    }

def get_valid_roadmap_metadata():
    return {
        "roadmap": [
            {"id": "Phase_109", "status": "OPEN"}
        ]
    }

def get_valid_telemetry_metadata():
    return {
        "telemetry": [
            {"type": "HEARTBEAT", "level": "INFO"}
        ]
    }

def run_sweep(fail_mode=False):
    """
    Executes all governance agents in a read-only mode and generates a unified assessment.
    Never calls brokers, executes trades, or mutates repository files.
    """
    auditor = GovernanceAuditorAgent()
    certifier = CertificationAgent()
    intelligence = RepositoryIntelligenceAgent()
    commander = OperationsCommanderAgent()
    coordinator = UnifiedGovernanceCoordinator()

    if fail_mode:
        # Pass None to force the fail-closed logic in all agents
        audit_res = auditor.audit_metadata(None)
        cert_res = certifier.evaluate_readiness(None)
        intel_res = intelligence.analyze_roadmap(None)
        ops_res = commander.interpret_telemetry(None)
    else:
        # Pass canonically valid structural states
        audit_res = auditor.audit_metadata(get_valid_audit_metadata())
        cert_res = certifier.evaluate_readiness(get_valid_certification_metadata())
        intel_res = intelligence.analyze_roadmap(get_valid_roadmap_metadata())
        ops_res = commander.interpret_telemetry(get_valid_telemetry_metadata())

    report = coordinator.aggregate_governance_state(
        audit_res, cert_res, intel_res, ops_res
    )
    return report

if __name__ == "__main__":
    fail_mode = "--fail-closed" in sys.argv
    report = run_sweep(fail_mode=fail_mode)
    
    print("="*50)
    print("AI GOVERNANCE LAYER: UNIFIED SWEEP")
    print("="*50)
    print(f"Governance Status: {report.governance_status}")
    print(f"Readiness Score: {report.readiness_score}")
    print(f"Authority Status: {report.authority_status}")
    print(f"Certification Status: {report.certification_status}")
    
    if report.governance_status != "READY":
        print("\nFindings:")
        for f in report.critical_findings + report.high_findings + report.medium_findings + report.low_findings:
            print(f" - [{f.severity}] {f.source}: {f.issue}")
        sys.exit(1)
    else:
        print("\nAll governance checks passed successfully.")
        sys.exit(0)
