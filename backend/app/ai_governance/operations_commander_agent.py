from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class IncidentSummary:
    severity: str
    description: str
    escalation_level: str
    runbook_references: List[str]

@dataclass
class OperationsResult:
    status: str  # "OK", "FAIL_CLOSED", "INCIDENT"
    incidents: List[IncidentSummary]

class OperationsCommanderAgent:
    """
    Read-only agent that interprets operational telemetry, alerts, and runbooks.
    It does not execute trades, interact with brokers, or mutate files.
    """

    def interpret_telemetry(self, metadata: Optional[Dict]) -> OperationsResult:
        """
        Evaluates operational telemetry metadata.
        Fails closed if inputs are missing or malformed.
        """
        if metadata is None:
            return OperationsResult(
                status="FAIL_CLOSED",
                incidents=[IncidentSummary("CRITICAL", "Missing telemetry metadata entirely.", "L3", [])]
            )

        if not isinstance(metadata, dict):
            return OperationsResult(
                status="FAIL_CLOSED",
                incidents=[IncidentSummary("CRITICAL", "Malformed telemetry metadata: must be a dict.", "L3", [])]
            )

        telemetry = metadata.get("telemetry", [])
        if not isinstance(telemetry, list):
            return OperationsResult(
                status="FAIL_CLOSED",
                incidents=[IncidentSummary("CRITICAL", "Malformed metadata: 'telemetry' must be a list.", "L3", [])]
            )

        incidents = []
        
        for item in telemetry:
            event_type = item.get("type")
            if not event_type:
                incidents.append(IncidentSummary(
                    severity="HIGH",
                    description="Telemetry event missing type",
                    escalation_level="L2",
                    runbook_references=[]
                ))
                continue
            
            level = item.get("level", "INFO")
            if level in ["ERROR", "CRITICAL", "P0", "P1"]:
                escalation = "L3" if level in ["CRITICAL", "P0"] else "L2"
                incidents.append(IncidentSummary(
                    severity=level,
                    description=item.get("description", f"Unspecified incident of type {event_type}"),
                    escalation_level=escalation,
                    runbook_references=item.get("runbook_mappings", ["GENERAL_INCIDENT_RUNBOOK"])
                ))
            elif level == "WARNING":
                incidents.append(IncidentSummary(
                    severity="WARNING",
                    description=item.get("description", f"Warning event: {event_type}"),
                    escalation_level="L1",
                    runbook_references=item.get("runbook_mappings", [])
                ))

        if incidents:
            return OperationsResult(status="INCIDENT", incidents=incidents)

        return OperationsResult(status="OK", incidents=[])
