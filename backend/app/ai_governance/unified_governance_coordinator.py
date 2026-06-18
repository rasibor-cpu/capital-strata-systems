from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from backend.app.ai_governance.governance_auditor_agent import AuditResult, AuditFinding
from backend.app.ai_governance.certification_agent import ReadinessSummary
from backend.app.ai_governance.repository_intelligence_agent import RoadmapSummary
from backend.app.ai_governance.operations_commander_agent import OperationsResult

@dataclass
class ConsolidatedFinding:
    source: str
    severity: str
    issue: str

@dataclass
class UnifiedGovernanceReport:
    governance_status: str  # "READY", "NOT_READY", "FAIL_CLOSED"
    readiness_score: int
    critical_findings: List[ConsolidatedFinding] = field(default_factory=list)
    high_findings: List[ConsolidatedFinding] = field(default_factory=list)
    medium_findings: List[ConsolidatedFinding] = field(default_factory=list)
    low_findings: List[ConsolidatedFinding] = field(default_factory=list)
    authority_status: str = "UNKNOWN"
    certification_status: str = "UNKNOWN"
    roadmap_status: str = "UNKNOWN"
    operations_status: str = "UNKNOWN"
    recommended_actions: List[str] = field(default_factory=list)

class UnifiedGovernanceCoordinator:
    """
    Read-only coordinator that aggregates the outputs from the AI Governance Agents.
    Calculates overall readiness score, classifies findings by severity, and fails closed
    if inputs are malformed or missing.
    """

    def _fail_closed(self, reason: str) -> UnifiedGovernanceReport:
        return UnifiedGovernanceReport(
            governance_status="FAIL_CLOSED",
            readiness_score=0,
            critical_findings=[ConsolidatedFinding(source="COORDINATOR", severity="CRITICAL", issue=reason)],
            recommended_actions=["Halt all operations until governance metadata is restored and valid."]
        )

    def aggregate_governance_state(
        self,
        audit_output: Any,
        certification_output: Any,
        intelligence_output: Any,
        operations_output: Any
    ) -> UnifiedGovernanceReport:
        
        # Verify types
        if not isinstance(audit_output, AuditResult):
            return self._fail_closed("Invalid or missing AuditResult.")
        if not isinstance(certification_output, ReadinessSummary):
            return self._fail_closed("Invalid or missing ReadinessSummary.")
        if not isinstance(intelligence_output, RoadmapSummary):
            return self._fail_closed("Invalid or missing RoadmapSummary.")
        if not isinstance(operations_output, OperationsResult):
            return self._fail_closed("Invalid or missing OperationsResult.")
            
        report = UnifiedGovernanceReport(
            governance_status="NOT_READY",
            readiness_score=100,
            authority_status=audit_output.status,
            certification_status=certification_output.status,
            roadmap_status=intelligence_output.status,
            operations_status=operations_output.status,
        )

        # Aggregate Authority Findings
        if audit_output.status == "FAIL_CLOSED":
            report.critical_findings.append(ConsolidatedFinding("AUDITOR", "CRITICAL", "Auditor failed closed."))
            report.readiness_score = 0
        else:
            for f in audit_output.findings:
                finding = ConsolidatedFinding("AUDITOR", f.severity, f.issue)
                self._route_finding(report, finding)

        # Aggregate Certification Findings
        if certification_output.status == "FAIL_CLOSED":
            report.critical_findings.append(ConsolidatedFinding("CERTIFIER", "CRITICAL", "Certifier failed closed."))
            report.readiness_score = 0
        else:
            for f in certification_output.findings:
                finding = ConsolidatedFinding("CERTIFIER", f.severity, f.issue)
                self._route_finding(report, finding)

        # Aggregate Intelligence Findings
        if intelligence_output.status == "FAIL_CLOSED":
            report.critical_findings.append(ConsolidatedFinding("INTELLIGENCE", "CRITICAL", "Intelligence failed closed."))
            report.readiness_score = 0
        else:
            for f in intelligence_output.findings:
                finding = ConsolidatedFinding("INTELLIGENCE", f.severity, f.issue)
                self._route_finding(report, finding)

        # Aggregate Operations Findings
        if operations_output.status == "FAIL_CLOSED":
            report.critical_findings.append(ConsolidatedFinding("OPERATIONS", "CRITICAL", "Operations failed closed."))
            report.readiness_score = 0
        else:
            for inc in operations_output.incidents:
                finding = ConsolidatedFinding("OPERATIONS", inc.severity, inc.description)
                self._route_finding(report, finding)

        # Calculate Status
        if report.critical_findings:
            report.governance_status = "FAIL_CLOSED"
            report.readiness_score = 0
        elif report.high_findings:
            report.governance_status = "NOT_READY"
        else:
            report.governance_status = "READY"

        # Generate Recommendations
        if report.governance_status == "FAIL_CLOSED":
            report.recommended_actions.append("Immediately resolve critical failures preventing governance agent operation.")
        elif report.governance_status == "NOT_READY":
            report.recommended_actions.append("Address high-severity governance findings before proceeding.")
        else:
            report.recommended_actions.append("Governance checks passed. System is ready.")

        return report

    def _route_finding(self, report: UnifiedGovernanceReport, finding: ConsolidatedFinding):
        sev = finding.severity.upper()
        if sev in ["CRITICAL", "P0"]:
            report.critical_findings.append(finding)
            report.readiness_score = 0
        elif sev in ["HIGH", "P1", "ERROR"]:
            report.high_findings.append(finding)
            report.readiness_score = max(0, report.readiness_score - 25)
        elif sev in ["MEDIUM", "WARNING", "P2"]:
            report.medium_findings.append(finding)
            report.readiness_score = max(0, report.readiness_score - 10)
        else:
            report.low_findings.append(finding)
            report.readiness_score = max(0, report.readiness_score - 5)
