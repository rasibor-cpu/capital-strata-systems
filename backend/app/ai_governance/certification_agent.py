from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class CertificationFinding:
    severity: str
    issue: str
    reference_id: str

@dataclass
class ReadinessSummary:
    status: str  # "READY", "FAIL_CLOSED", "NOT_READY"
    findings: List[CertificationFinding]

class CertificationAgent:
    """
    Read-only agent that monitors certification completeness and readiness status.
    It does not execute trades, interact with brokers, or mutate files.
    """

    def __init__(self):
        self.required_phases = [
            "107A", "107B", "107C", "107D", "107E", "107F",
            "108A", "108B", "108C", "108D", "108E"
        ]

    def evaluate_readiness(self, metadata: Optional[Dict]) -> ReadinessSummary:
        """
        Evaluates certification metadata for completeness and validity.
        Fails closed if inputs are missing or malformed.
        """
        if metadata is None:
            return ReadinessSummary(
                status="FAIL_CLOSED",
                findings=[CertificationFinding("CRITICAL", "Missing certification metadata entirely.", "system")]
            )

        if not isinstance(metadata, dict) or "certifications" not in metadata:
            return ReadinessSummary(
                status="FAIL_CLOSED",
                findings=[CertificationFinding("CRITICAL", "Malformed metadata: missing 'certifications' key.", "schema")]
            )

        findings = []
        certifications = metadata.get("certifications", [])

        if not isinstance(certifications, list):
            return ReadinessSummary(
                status="FAIL_CLOSED",
                findings=[CertificationFinding("CRITICAL", "Malformed metadata: 'certifications' must be a list.", "schema")]
            )

        # Build map of available certs
        cert_map = {}
        for cert in certifications:
            ref_id = cert.get("reference_id")
            if not ref_id:
                findings.append(CertificationFinding("HIGH", "Certification missing reference_id", "unknown"))
                continue
            cert_map[ref_id] = cert

        # Check required phases
        for required_phase in self.required_phases:
            if required_phase not in cert_map:
                findings.append(CertificationFinding(
                    severity="HIGH",
                    issue=f"Missing required certification: {required_phase}",
                    reference_id=required_phase
                ))
            else:
                cert = cert_map[required_phase]
                status = cert.get("status")
                if status == "EXPIRED" or status == "DEPRECATED":
                    findings.append(CertificationFinding(
                        severity="HIGH",
                        issue=f"Certification is {status}: {required_phase}",
                        reference_id=required_phase
                    ))
                elif status != "APPROVED":
                    findings.append(CertificationFinding(
                        severity="MEDIUM",
                        issue=f"Certification incomplete or unapproved: {required_phase} (status: {status})",
                        reference_id=required_phase
                    ))
                
                # Check chains (if a cert claims it supersedes or depends on another)
                depends_on = cert.get("depends_on", [])
                for dep in depends_on:
                    if dep not in cert_map or cert_map[dep].get("status") != "APPROVED":
                        findings.append(CertificationFinding(
                            severity="HIGH",
                            issue=f"Incomplete certification chain: {required_phase} depends on {dep} which is not APPROVED.",
                            reference_id=required_phase
                        ))

        if findings:
            return ReadinessSummary(status="NOT_READY", findings=findings)

        return ReadinessSummary(status="READY", findings=[])
