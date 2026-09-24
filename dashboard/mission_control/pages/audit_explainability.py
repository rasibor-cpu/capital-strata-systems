from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, page_header, section


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def _first_recommendation(recommendations: dict) -> dict:
    rows = recommendations.get("recommendations")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]
    return {}


def _committee_summary_rows(committee: dict) -> list[dict]:
    rows = committee.get("committees")
    if not isinstance(rows, list):
        return []
    summary = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        summary.append({
            "committee": row.get("committee"),
            "outcome": row.get("outcome"),
            "reason": row.get("reason"),
            "freshness": row.get("freshness"),
        })
    return summary


def _source_consistency_summary(value: object) -> object:
    if isinstance(value, dict):
        return value.get("status") or value.get("freshness") or "RECORDED"
    return value


def render(state: dict) -> str:
    audit = section(state, "audit")
    explanation = section(state, "decision_explanation")
    committee = section(state, "committee_view")
    counterfactuals = section(state, "counterfactuals")
    recommendations = section(state, "recommendation_panel")
    evidence = section(state, "evidence_graph")
    audit_console = section(state, "audit_console")
    history = section(state, "change_history_console")
    return (
        page_header("Audit and Explainability", "Read-only explanations, rules, metrics, source modules, evidence, warnings, failures, and operator actions.")
        + '<nav class="mc-page-jump" aria-label="Audit and Explainability sections">'
          '<a href="#mc-audit-decision">Decision</a>'
          '<a href="#mc-audit-committee">Committee</a>'
          '<a href="#mc-audit-evidence">Evidence</a>'
          '<a href="#mc-audit-history">History</a>'
          '</nav>'
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-audit-decision", detail_table("Decision Explanation", {
            "decision": explanation.get("decision"),
            "plain_language": explanation.get("plain_language"),
            "blocking_subsystem": explanation.get("blocking_subsystem"),
            "blocking_rule": explanation.get("blocking_rule"),
            "required_improvement": explanation.get("required_improvement"),
        }))
        + _anchor_panel("mc-audit-committee", detail_table("Committee Snapshot", _committee_summary_rows(committee)))
        + _anchor_panel("mc-audit-guidance", detail_table("Operator Guidance", {
            "top_action": _first_recommendation(recommendations).get("action", "UNAVAILABLE"),
            "top_reason": _first_recommendation(recommendations).get("reason", "UNAVAILABLE"),
            "authority": _first_recommendation(recommendations).get("authority", "UNAVAILABLE"),
            "changes_execution": _first_recommendation(recommendations).get("changes_execution", False),
            "counterfactual_count": len(counterfactuals.get("counterfactuals", [])) if isinstance(counterfactuals.get("counterfactuals"), list) else 0,
            "warning_count": len(audit.get("warnings", [])) if isinstance(audit.get("warnings"), list) else 0,
            "failure_count": len(audit.get("failures", [])) if isinstance(audit.get("failures"), list) else 0,
        }))
        + _anchor_panel("mc-audit-evidence", detail_table("Evidence Snapshot", {
            "status": evidence.get("status"),
            "source_consistency": _source_consistency_summary(evidence.get("source_consistency")),
            "node_count": len(evidence.get("nodes", [])) if isinstance(evidence.get("nodes"), list) else 0,
            "edge_count": len(evidence.get("edges", [])) if isinstance(evidence.get("edges"), list) else 0,
        }))
        + _evidence_panel("mc-audit-counterfactuals", "Show counterfactual evidence", detail_table("Counterfactuals", counterfactuals.get("counterfactuals", [])))
        + _evidence_panel("mc-audit-recommendations", "Show recommendation evidence", detail_table("Recommendations", recommendations.get("recommendations", [])))
        + _evidence_panel("mc-audit-graph", "Show evidence graph", detail_table("Evidence Graph", {
            "status": evidence.get("status"),
            "nodes": evidence.get("nodes"),
            "edges": evidence.get("edges"),
            "source_consistency": evidence.get("source_consistency"),
        }))
        + _evidence_panel("mc-audit-decision-evidence", "Show full decision evidence", detail_table("Decision Evidence", {
            "decision_explanations": audit.get("decision_explanations"),
            "rules_evaluated": audit.get("rules_evaluated"),
            "supporting_metrics": audit.get("supporting_metrics"),
            "source_modules": audit.get("source_modules"),
        }))
        + _evidence_panel("mc-audit-trail", "Show audit trail", detail_table("Audit Trail", {
            "correlation_ids": audit.get("correlation_ids"),
            "event_ids": audit.get("event_ids"),
            "audit_evidence": audit.get("audit_evidence"),
            "warnings": audit.get("warnings"),
            "failures": audit.get("failures"),
            "operator_actions": audit.get("operator_actions"),
        }))
        + _evidence_panel("mc-audit-center", "Show audit center evidence", detail_table("Audit Center", {
            "configuration_changes": audit_console.get("configuration_changes"),
            "runtime_events": audit_console.get("runtime_events"),
            "operator_actions": audit_console.get("operator_actions"),
            "certification_events": audit_console.get("certification_events"),
            "committee_actions": audit_console.get("committee_actions"),
            "decision_history": audit_console.get("decision_history"),
            "deletion_enabled": audit_console.get("deletion_enabled"),
        }))
        + _evidence_panel("mc-audit-history", "Show change history", detail_table("Change History", history.get("changes", [])))
        + '</div>'
    )
