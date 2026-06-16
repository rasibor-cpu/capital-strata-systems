from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class AuditFinding:
    severity: str
    issue: str
    component: str

@dataclass
class AuditResult:
    status: str  # "PASS", "FAIL_CLOSED", "FINDINGS"
    findings: List[AuditFinding]

class GovernanceAuditorAgent:
    """
    Read-only agent that inspects governance evidence and reports authority-drift risks.
    It does not execute trades, interact with brokers, or mutate files.
    """

    def __init__(self):
        self.authority_register_required = True

    def audit_metadata(self, metadata: Optional[Dict]) -> AuditResult:
        """
        Audits the provided governance metadata.
        Fails closed if the metadata is missing or does not contain the authority register.
        """
        if metadata is None:
            return AuditResult(
                status="FAIL_CLOSED",
                findings=[AuditFinding("CRITICAL", "Missing governance metadata entirely.", "system")]
            )

        if "authority_register" not in metadata:
            return AuditResult(
                status="FAIL_CLOSED",
                findings=[AuditFinding("CRITICAL", "Missing authority register in metadata.", "authority_register")]
            )

        findings = []
        authority_register = metadata.get("authority_register", {})
        declarations = metadata.get("declarations", [])
        certifications = metadata.get("certifications", [])

        # Detect duplicate authority declarations
        seen_declarations = set()
        for decl in declarations:
            if decl in seen_declarations:
                findings.append(AuditFinding(
                    severity="HIGH",
                    issue=f"Duplicate authority declaration detected: {decl}",
                    component="declarations"
                ))
            seen_declarations.add(decl)

        # Detect incomplete certification references
        for cert in certifications:
            if not cert.get("reference_id") or not cert.get("status"):
                findings.append(AuditFinding(
                    severity="MEDIUM",
                    issue=f"Incomplete certification reference: {cert}",
                    component="certifications"
                ))

        if findings:
            return AuditResult(status="FINDINGS", findings=findings)

        return AuditResult(status="PASS", findings=[])
