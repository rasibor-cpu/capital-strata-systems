from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class RoadmapFinding:
    severity: str
    issue: str
    item_id: str

@dataclass
class RoadmapSummary:
    status: str  # "VALID", "FAIL_CLOSED", "FINDINGS"
    findings: List[RoadmapFinding]
    completed_items: List[str]
    open_items: List[str]

class RepositoryIntelligenceAgent:
    """
    Read-only agent that provides repository analysis, roadmap tracking, and 
    authority drift detection support. It does not execute trades, interact with brokers,
    or mutate files.
    """

    def analyze_roadmap(self, metadata: Optional[Dict]) -> RoadmapSummary:
        """
        Evaluates repository and roadmap metadata.
        Fails closed if inputs are missing or malformed.
        """
        if metadata is None:
            return RoadmapSummary(
                status="FAIL_CLOSED",
                findings=[RoadmapFinding("CRITICAL", "Missing repository metadata entirely.", "system")],
                completed_items=[],
                open_items=[]
            )

        if not isinstance(metadata, dict) or "roadmap" not in metadata:
            return RoadmapSummary(
                status="FAIL_CLOSED",
                findings=[RoadmapFinding("CRITICAL", "Malformed metadata: missing 'roadmap' key.", "schema")],
                completed_items=[],
                open_items=[]
            )

        roadmap = metadata.get("roadmap", [])
        if not isinstance(roadmap, list):
            return RoadmapSummary(
                status="FAIL_CLOSED",
                findings=[RoadmapFinding("CRITICAL", "Malformed metadata: 'roadmap' must be a list.", "schema")],
                completed_items=[],
                open_items=[]
            )

        findings = []
        completed = []
        open_items = []
        seen_items = set()

        for item in roadmap:
            item_id = item.get("id")
            if not item_id:
                findings.append(RoadmapFinding("HIGH", "Roadmap item missing id", "unknown"))
                continue
            
            # Detect duplicate roadmap entries
            if item_id in seen_items:
                findings.append(RoadmapFinding("HIGH", f"Duplicate roadmap entry detected: {item_id}", item_id))
            seen_items.add(item_id)

            status = item.get("status")
            if status == "COMPLETED":
                completed.append(item_id)
            else:
                open_items.append(item_id)

        # Authority drift risk detection
        drift_risks = metadata.get("authority_drift_risks", [])
        if isinstance(drift_risks, list):
            for risk in drift_risks:
                findings.append(RoadmapFinding("HIGH", f"Authority drift risk flagged: {risk}", "repository"))

        if findings:
            return RoadmapSummary(status="FINDINGS", findings=findings, completed_items=completed, open_items=open_items)

        return RoadmapSummary(status="VALID", findings=[], completed_items=completed, open_items=open_items)
