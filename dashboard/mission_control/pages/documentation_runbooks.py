from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, page_header, section, split_panels


def render(state: dict) -> str:
    docs = section(state, "documentation")
    return (
        page_header("Documentation / Runbooks", "Safe internal document index for architecture, governance, release, certification, incident, rollback, and operator references.")
        + split_panels(
            detail_table("Architecture And Governance", {
                "architecture": docs.get("architecture"),
                "governance": docs.get("governance"),
                "release_reports": docs.get("release_reports"),
                "certification_reports": docs.get("certification_reports"),
            }),
            detail_table("Operational Runbooks", {
                "operator_runbooks": docs.get("operator_runbooks"),
                "rollback_instructions": docs.get("rollback_instructions"),
                "broker_onboarding_guides": docs.get("broker_onboarding_guides"),
                "incident_procedures": docs.get("incident_procedures"),
                "rc1_validation_reports": docs.get("rc1_validation_reports"),
                "options_income_documentation": docs.get("options_income_documentation"),
                "browser_paths_expose_absolute_paths": docs.get("browser_paths_expose_absolute_paths"),
            }),
        )
    )
