"""
CSS Institutional Audit Intelligence Engine

Consolidates and filters historical events from the system timeline,
event log, and other diagnostic outputs into institutional audit trails.
"""

from typing import Dict, Any, List
from backend.events.event_models import Event

class InstitutionalAuditIntelligence:
    """
    Consolidates audit trails for decisions, runtime events, broker status,
    recommendations, portfolio changes, governance checks, and learning signals.
    """
    def __init__(self, visibility_layer: Any = None):
        self.visibility_layer = visibility_layer

    def compile_audit_trail(self, limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """
        Consolidates active events and partitions them into logical audit trails.
        """
        audit_trail = {
            "decisions": [],
            "runtime_events": [],
            "broker_status": [],
            "recommendations": [],
            "portfolio_changes": [],
            "governance_checks": [],
            "learning_signals": []
        }

        if not self.visibility_layer:
            return audit_trail

        events = []
        try:
            # Query recent timeline events and wildcard store events
            events.extend(self.visibility_layer.get_recent_timeline_events(limit=limit))
            events.extend(self.visibility_layer.get_recent_events(limit=limit))
        except Exception:
            pass

        # De-duplicate events by ID
        unique_events = {}
        for e in events:
            if isinstance(e, Event) and e.event_id not in unique_events:
                unique_events[e.event_id] = e

        for event in unique_events.values():
            etype = event.event_type.upper()
            payload = event.payload or {}
            
            # Format single record
            record = {
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "severity": event.severity,
                "source": event.source,
                "message": payload.get("message", f"{etype} recorded"),
                "details": payload
            }

            # Map to category
            if etype in {"TRADE_APPROVED", "TRADE_REJECTED", "DECISION_EVALUATED"}:
                audit_trail["decisions"].append(record)
            elif etype in {"RUNTIME_STARTED", "RUNTIME_STOPPED", "RECOVERY_STARTED", "RECOVERY_COMPLETE", "HEARTBEAT"}:
                audit_trail["runtime_events"].append(record)
            elif etype in {"BROKER_CONNECTED", "BROKER_DISCONNECTED", "HEALTH_CHECK_RESULT", "CONNECTIVITY_CERTIFICATION"}:
                audit_trail["broker_status"].append(record)
            elif etype in {"EXECUTIVE_RECOMMENDATION", "REPORT_GENERATED", "REPORT_QUEUED"}:
                audit_trail["recommendations"].append(record)
            elif etype in {"PORTFOLIO_CONSTRUCTION_COMPLETED", "CAPITAL_ROTATED", "PORTFOLIO_REBALANCED"}:
                audit_trail["portfolio_changes"].append(record)
            elif etype in {"GOVERNANCE_CHECK_PASSED", "GOVERNANCE_CHECK_FAILED", "SAFETY_GATE_TRIGGERED"}:
                audit_trail["governance_checks"].append(record)
            elif etype in {"LEARNING_FEEDBACK_RECEIVED", "STRATEGY_PERFORMANCE_UPDATED", "LEAGUE_TABLE_UPDATED"}:
                audit_trail["learning_signals"].append(record)
            else:
                # Default categorisation fallback
                if "risk" in etype or "safety" in etype:
                    audit_trail["governance_checks"].append(record)
                elif "broker" in etype or "oanda" in etype or "coinbase" in etype:
                    audit_trail["broker_status"].append(record)
                else:
                    audit_trail["runtime_events"].append(record)

        # Sort chronological
        for key in audit_trail:
            audit_trail[key].sort(key=lambda x: x["timestamp"])

        return audit_trail

    def export_audit_trail_report(self) -> str:
        """
        Exports the compiled audit trail as a beautiful institutional markdown report.
        """
        trail = self.compile_audit_trail()
        
        md = []
        md.append("# Capital Strata Systems (CSS) Institutional Audit Report")
        md.append("## Production Audit Trail Consolidation\n")
        
        categories = [
            ("decisions", "Decisions & Pre-Trade Gate Evaluations"),
            ("runtime_events", "System Runtime & Recovery Events"),
            ("broker_status", "Broker Integrations & Connection Status"),
            ("recommendations", "Executive Reports & Policy Recommendations"),
            ("portfolio_changes", "Portfolio Construction & Capital Rotation"),
            ("governance_checks", "Governance Safety Gates & Compliance Limits"),
            ("learning_signals", "Autonomous Learning Loops & Feedback Signals")
        ]

        for key, name in categories:
            md.append(f"### {name}")
            records = trail[key]
            if not records:
                md.append("*No logged events in this category.*\n")
            else:
                md.append("| Time | Event ID | Severity | Message |")
                md.append("| --- | --- | --- | --- |")
                for r in records:
                    import time
                    formatted_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["timestamp"]))
                    msg = r["message"].replace("\n", " ")
                    md.append(f"| {formatted_time} | `{r['event_id'][:8]}` | {r['severity']} | {msg} |")
                md.append("")

        return "\n".join(md)
