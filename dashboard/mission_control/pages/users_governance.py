from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, split_panels


def render(state: dict) -> str:
    governance = section(state, "governance")
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
        )
    )
