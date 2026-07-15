from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    governance = section(state, "governance")
    rbac = section(state, "rbac_console")
    operator = section(state, "operator_console")
    approvals = section(state, "approval_workflow_console")
    summary = section(state, "governance_summary_console")
    return (
        page_header("Users and Governance", "Read-only user, role, unit, session, permissions, RBAC, allowed modes, and governance status.")
        + metric_grid(
            (
                ("Current User", governance.get("current_user"), "neutral"),
                ("Role", governance.get("role"), "neutral"),
                ("Unit", governance.get("unit"), "neutral"),
                ("Governance", governance.get("governance_status"), governance.get("governance_status")),
                ("RBAC", governance.get("rbac_summary"), governance.get("rbac_summary")),
            )
        )
        + split_panels(
            detail_table("Session", {
                "session": governance.get("session"),
                "session_age": governance.get("session_age"),
                "authentication_source": governance.get("authentication_source"),
                "allowed_engine_modes": governance.get("allowed_engine_modes"),
            }),
            detail_table("Permissions", governance.get("permissions", {})),
            detail_table("RBAC Console", {
                "current_role": rbac.get("current_role"),
                "roles": rbac.get("roles"),
                "role_editing": rbac.get("role_editing"),
                "write_routes_enabled": rbac.get("write_routes_enabled"),
                "state_hash": rbac.get("state_hash"),
            }),
            detail_table("Operator Console", {
                "operator": operator.get("operator"),
                "role": operator.get("role"),
                "unit": operator.get("unit"),
                "session": operator.get("session"),
                "available_actions": operator.get("available_actions"),
                "disabled_actions": operator.get("disabled_actions"),
            }),
            detail_table("Approval Workflows", approvals.get("workflows", [])),
            detail_table("Governance Summary", {
                "security_posture": summary.get("security_posture"),
                "audit_posture": summary.get("audit_posture"),
                "approval_posture": summary.get("approval_posture"),
                "configuration_posture": summary.get("configuration_posture"),
                "certification_posture": summary.get("certification_posture"),
            }),
        )
    )
