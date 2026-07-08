from __future__ import annotations

import json
from typing import Any


class ExecutiveSummaryFormatter:
    """Formatter to convert aggregated brief payloads into JSON, Markdown, and Console text formats."""

    def to_json(self, brief: dict[str, Any], *, indent: int = 2) -> str:
        """Serialize the aggregated brief dictionary into formatted JSON."""
        return json.dumps(brief, indent=indent)

    def to_markdown(self, brief: dict[str, Any]) -> str:
        """Convert the brief dictionary into a polished executive markdown report."""
        status = brief.get("overall_status", "DATA UNAVAILABLE").upper()
        
        # Select status color alert
        alert_type = "NOTE"
        if status == "GREEN":
            alert_type = "TIP"
        elif status == "RED" or status == "DATA UNAVAILABLE":
            alert_type = "CAUTION"
        elif status in {"AMBER", "PARTIAL", "DEFENSIVE"}:
            alert_type = "WARNING"

        md = []
        md.append(f"# CSS Executive Decision Brief\n")
        
        md.append(f"> [!{alert_type}]")
        md.append(f"> **Overall System Status: {status}**")
        md.append(f"> Generated as advisory-only presentation layer. Live trading gates remain locked.\n")

        md.append("## System Overview")
        md.append(f"- **Market Regime**: {brief.get('market_regime', 'UNKNOWN')}")
        md.append(f"- **Decision Confidence**: {brief.get('decision_confidence', 0.0):.1f}%")
        md.append(f"- **Runtime Health**: {brief.get('runtime_health', 'UNKNOWN')}")
        md.append(f"- **Portfolio Quality**: {brief.get('portfolio_quality', 0.0):.1f}%")
        md.append(f"- **Preferred Portfolio Scenario**: {brief.get('preferred_portfolio', 'UNKNOWN')}\n")

        md.append("## Broker Health")
        details = brief.get("broker_health_details", {})
        if details:
            for broker, health in details.items():
                md.append(f"- **{broker}**: {health}")
        else:
            md.append(f"- Status: {brief.get('broker_health', 'DATA UNAVAILABLE')}")
        md.append("")

        md.append("## Investment Committee Evaluation")
        md.append(f"- **Recommendation**: **{brief.get('investment_committee', 'REJECT')}**")
        tally = brief.get("committee_vote", {})
        md.append(f"- **Committee Vote Tally**: Approve: {tally.get('approve', 0)} | Conditional: {tally.get('conditional', 0)} | Reject: {tally.get('reject', 0)}\n")

        md.append("## Top Opportunities")
        for opp in brief.get("top_opportunities", []):
            md.append(f"- {opp}")
        if not brief.get("top_opportunities"):
            md.append("- No premium tactical opportunities identified.")
        md.append("")

        md.append("## Top Risks")
        for risk in brief.get("top_risks", []):
            md.append(f"- {risk}")
        if not brief.get("top_risks"):
            md.append("- No high priority risks identified.")
        md.append("")

        md.append("## Recommended Actions")
        for action in brief.get("recommended_actions", []):
            md.append(f"- {action}")
        if not brief.get("recommended_actions"):
            md.append("- No actions required.")
        md.append("")

        if brief.get("operational_warnings"):
            md.append("## Operational Warnings")
            for warning in brief.get("operational_warnings", []):
                md.append(f"> [!WARNING]")
                md.append(f"> {warning}")
            md.append("")

        md.append("## Ingested Components & Integrity")
        integ = brief.get("integration", {})
        md.append(f"- **Adaptive Strategy Intelligence (157A)**: {'CONSUMED' if integ.get('phase157a_consumed') else 'NOT CONSUMED'}")
        md.append(f"- **Portfolio Construction (157B)**: {'CONSUMED' if integ.get('phase157b_consumed') else 'NOT CONSUMED'}")
        md.append(f"- **Institutional Portfolio Optimizer (157C)**: {'CONSUMED' if integ.get('phase157c_consumed') else 'NOT CONSUMED'}")
        md.append(f"- **Investment Committee (158A)**: {'CONSUMED' if integ.get('phase158a_consumed') else 'NOT CONSUMED'}")
        md.append(f"- **Decision Confidence**: {'CONSUMED' if integ.get('decision_confidence_consumed') else 'NOT CONSUMED'}")
        md.append(f"- **Broker Health**: {'CONSUMED' if integ.get('broker_health_consumed') else 'NOT CONSUMED'}\n")

        md.append("## Advisory Execution Status")
        exec_status = brief.get("execution_status", {})
        md.append(f"- **Execution Authority**: {exec_status.get('execution_authority', 'NOT GRANTED')}")
        md.append(f"- **Live Trading**: {exec_status.get('live_trading', 'BLOCKED')}")
        md.append(f"- **Broker Execution**: {exec_status.get('broker_execution', 'DISARMED')}")

        return "\n".join(md)

    def to_console(self, brief: dict[str, Any]) -> str:
        """Convert the brief dictionary into fixed-width ASCII console text matching presentation layout."""
        lines = []
        lines.append("==================================================")
        lines.append("CSS EXECUTIVE DECISION BRIEF")
        lines.append("==================================================")
        
        lines.append("Overall Status")
        lines.append(brief.get("overall_status", "DATA UNAVAILABLE"))
        lines.append("")

        lines.append("Market Regime")
        lines.append(brief.get("market_regime", "UNKNOWN"))
        lines.append("")

        lines.append("Decision Confidence")
        lines.append(f"{brief.get('decision_confidence', 0.0):.1f}%")
        lines.append("")

        lines.append("Broker Health")
        details = brief.get("broker_health_details", {})
        if details:
            for broker, health in details.items():
                lines.append(broker)
                lines.append(health)
        else:
            lines.append(brief.get("broker_health", "DATA UNAVAILABLE"))
        lines.append("")

        lines.append("Runtime Health")
        lines.append(brief.get("runtime_health", "UNKNOWN"))
        lines.append("")

        lines.append("Portfolio Quality")
        lines.append(f"{brief.get('portfolio_quality', 0.0):.1f}%")
        lines.append("")

        lines.append("Preferred Portfolio")
        lines.append(brief.get("preferred_portfolio", "UNKNOWN"))
        lines.append("")

        lines.append("Investment Committee")
        lines.append(brief.get("investment_committee", "REJECT"))
        lines.append("")

        lines.append("Committee Vote")
        tally = brief.get("committee_vote", {})
        lines.append(f"Approve: {tally.get('approve', 0)}")
        lines.append(f"Conditional: {tally.get('conditional', 0)}")
        lines.append(f"Reject: {tally.get('reject', 0)}")
        lines.append("")

        lines.append("Top Opportunities")
        opps = brief.get("top_opportunities", [])
        if opps:
            for opp in opps:
                lines.append(f"- {opp}")
        else:
            lines.append("- None identified.")
        lines.append("")

        lines.append("Top Risks")
        risks = brief.get("top_risks", [])
        if risks:
            for risk in risks:
                lines.append(f"- {risk}")
        else:
            lines.append("- None identified.")
        lines.append("")

        lines.append("Recommended Actions")
        actions = brief.get("recommended_actions", [])
        if actions:
            for action in actions:
                lines.append(f"- {action}")
        else:
            lines.append("- None identified.")
        lines.append("")

        lines.append("Execution Status")
        exec_status = brief.get("execution_status", {})
        lines.append("Execution Authority")
        lines.append(exec_status.get("execution_authority", "NOT GRANTED"))
        lines.append("Live Trading")
        lines.append(exec_status.get("live_trading", "BLOCKED"))
        lines.append("Broker Execution")
        lines.append(exec_status.get("broker_execution", "DISARMED"))

        lines.append("==================================================")
        return "\n".join(lines)
