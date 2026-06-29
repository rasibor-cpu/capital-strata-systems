"""
Deployment checklist builder for CSS production readiness certification.
"""

from typing import Any, Dict, List

from backend.certification.readiness_models import FAIL, PASS, WARNING, SubsystemReadiness


class DeploymentChecklist:
    """
    Converts subsystem readiness into operator-friendly deployment checklist rows.
    """

    REQUIRED_ITEMS = (
        ("Enterprise Event Bus", "Enterprise event bus health validated"),
        ("Notification Framework", "Notification framework health validated"),
        ("Reporting Framework", "Reporting framework health validated"),
        ("Operations Framework", "Operations framework health validated"),
        ("Metrics & Telemetry", "Metrics and telemetry health validated"),
        ("Dashboard Availability", "Dashboard read availability validated"),
        ("Event Subscription Integrity", "Event subscription integrity validated"),
        ("Runtime Supervisor", "Runtime supervisor status validated"),
        ("Executive Dashboard", "Executive dashboard status validated"),
    )

    def build(self, subsystems: List[SubsystemReadiness]) -> List[Dict[str, Any]]:
        by_name = {item.name: item for item in subsystems}
        checklist = []
        for name, label in self.REQUIRED_ITEMS:
            readiness = by_name.get(name)
            if readiness is None:
                status = WARNING
                score = 0.0
            else:
                status = readiness.status
                score = readiness.score
            checklist.append(
                {
                    "item": label,
                    "subsystem": name,
                    "status": status,
                    "score": score,
                    "complete": status == PASS,
                    "blocks_deployment": status == FAIL,
                }
            )
        return checklist
