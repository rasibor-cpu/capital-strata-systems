from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def render(state: dict) -> str:
    governance = section(state, "governance")
    rbac = section(state, "rbac_console")
    operator = section(state, "operator_console")
    approvals = section(state, "approval_workflow_console")
    summary = section(state, "governance_summary_console")
    return (
        page_header("Users and Governance", "Read-only user, role, unit, session, permissions, RBAC, allowed modes, and governance status.")
        + '<nav class="mc-page-jump" aria-label="Users and Governance sections">'
          '<a href="#mc-users-identity">Identity</a>'
          '<a href="#mc-users-session">Session</a>'
          '<a href="#mc-users-actions">Actions</a>'
          '<a href="#mc-users-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Current User", governance.get("current_user"), "neutral"),
                ("Role", governance.get("role"), "neutral"),
                ("Governance", governance.get("governance_status"), governance.get("governance_status")),
                ("RBAC", governance.get("rbac_summary"), governance.get("rbac_summary")),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-users-priority",
            aria_label="Users and Governance priority",
        )
        + metric_grid(
            (
                ("Unit", governance.get("unit"), "neutral"),
                ("Write Routes", rbac.get("write_routes_enabled"), rbac.get("write_routes_enabled")),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Users and Governance secondary metrics",
        )
        + '<section class="mc-panel"><h2>Governance Links</h2>'
          '<p><a href="/mission-control/credential-governance">Credential Governance</a> · '
          '<a href="/mission-control/enterprise-identity">Enterprise Identity &amp; Secrets</a> · '
          '<a href="/mission-control/enterprise-oauth">Enterprise OAuth</a> · '
          '<a href="/mission-control/enterprise-governance">Executive Governance</a> · '
          '<a href="/mission-control/production-readiness">Production Readiness</a></p></section>'
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-users-identity", detail_table("Identity & Governance Snapshot", {
            "current_user": governance.get("current_user"),
            "role": governance.get("role"),
            "unit": governance.get("unit"),
            "governance_status": governance.get("governance_status"),
            "rbac_summary": governance.get("rbac_summary"),
        }))
        + _anchor_panel("mc-users-session", detail_table("Session Snapshot", {
            "session": governance.get("session"),
            "session_age": governance.get("session_age"),
            "authentication_source": governance.get("authentication_source"),
            "allowed_engine_modes": governance.get("allowed_engine_modes"),
        }))
        + _anchor_panel("mc-users-actions", detail_table("Operator Action Snapshot", {
            "available_actions": operator.get("available_actions"),
            "disabled_actions": operator.get("disabled_actions"),
            "write_routes_enabled": rbac.get("write_routes_enabled"),
            "role_editing": rbac.get("role_editing"),
        }))
        + _anchor_panel("mc-users-governance", detail_table("Governance Summary", {
            "security_posture": summary.get("security_posture"),
            "audit_posture": summary.get("audit_posture"),
            "approval_posture": summary.get("approval_posture"),
            "configuration_posture": summary.get("configuration_posture"),
            "certification_posture": summary.get("certification_posture"),
        }))
        + _evidence_panel("mc-users-evidence", "Show permissions and RBAC evidence", detail_table("Permissions", governance.get("permissions", {})) + detail_table("RBAC Console", {
            "current_role": rbac.get("current_role"),
            "roles": rbac.get("roles"),
            "role_editing": rbac.get("role_editing"),
            "write_routes_enabled": rbac.get("write_routes_enabled"),
            "state_hash": rbac.get("state_hash"),
        }))
        + _evidence_panel("mc-users-operator-evidence", "Show operator-console evidence", detail_table("Operator Console", {
            "operator": operator.get("operator"),
            "role": operator.get("role"),
            "unit": operator.get("unit"),
            "session": operator.get("session"),
            "available_actions": operator.get("available_actions"),
            "disabled_actions": operator.get("disabled_actions"),
        }))
        + _evidence_panel("mc-users-approvals", "Show approval workflow evidence", detail_table("Approval Workflows", approvals.get("workflows", [])))
        + '</div>'
    )
