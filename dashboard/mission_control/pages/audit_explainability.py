from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, page_header, section, split_panels


def render(state: dict) -> str:
    audit = section(state, "audit")
    return (
        page_header("Audit and Explainability", "Read-only explanations, rules, metrics, source modules, evidence, warnings, failures, and operator actions.")
        + split_panels(
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
