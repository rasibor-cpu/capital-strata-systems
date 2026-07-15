from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, page_header, section, split_panels


def render(state: dict) -> str:
    audit = section(state, "audit")
    explanation = section(state, "decision_explanation")
    committee = section(state, "committee_view")
    counterfactuals = section(state, "counterfactuals")
    recommendations = section(state, "recommendation_panel")
    evidence = section(state, "evidence_graph")
    return (
        page_header("Audit and Explainability", "Read-only explanations, rules, metrics, source modules, evidence, warnings, failures, and operator actions.")
        + split_panels(
            detail_table("Decision Explanation", {
                "decision": explanation.get("decision"),
                "plain_language": explanation.get("plain_language"),
                "blocking_subsystem": explanation.get("blocking_subsystem"),
                "blocking_rule": explanation.get("blocking_rule"),
                "required_improvement": explanation.get("required_improvement"),
            }),
            detail_table("Committee View", committee.get("committees", [])),
            detail_table("Counterfactuals", counterfactuals.get("counterfactuals", [])),
            detail_table("Recommendations", recommendations.get("recommendations", [])),
            detail_table("Evidence Graph", {
                "status": evidence.get("status"),
                "nodes": evidence.get("nodes"),
                "edges": evidence.get("edges"),
                "source_consistency": evidence.get("source_consistency"),
            }),
            detail_table("Decision Evidence", {
                "decision_explanations": audit.get("decision_explanations"),
                "rules_evaluated": audit.get("rules_evaluated"),
                "supporting_metrics": audit.get("supporting_metrics"),
                "source_modules": audit.get("source_modules"),
            }),
            detail_table("Audit Trail", {
                "correlation_ids": audit.get("correlation_ids"),
                "event_ids": audit.get("event_ids"),
                "audit_evidence": audit.get("audit_evidence"),
                "warnings": audit.get("warnings"),
                "failures": audit.get("failures"),
                "operator_actions": audit.get("operator_actions"),
            }),
        )
    )
