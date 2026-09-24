from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section


def _count(value: object) -> object:
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    if value in (None, "", "DATA UNAVAILABLE"):
        return "UNAVAILABLE"
    return 1


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
    )


def render(state: dict) -> str:
    docs = section(state, "documentation")
    return (
        page_header("Documentation / Runbooks", "Safe internal document index for architecture, governance, release, certification, incident, rollback, and operator references.")
        + '<nav class="mc-page-jump" aria-label="Documentation and Runbooks sections">'
          '<a href="#mc-docs-coverage">Coverage</a>'
          '<a href="#mc-docs-ops">Operations</a>'
          '<a href="#mc-docs-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Architecture", _count(docs.get("architecture")), "neutral"),
                ("Governance", _count(docs.get("governance")), "neutral"),
                ("Release Reports", _count(docs.get("release_reports")), "neutral"),
                ("Certification", _count(docs.get("certification_reports")), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-docs-priority",
            aria_label="Documentation coverage priority",
        )
        + metric_grid(
            (
                ("Operator Runbooks", _count(docs.get("operator_runbooks")), "neutral"),
                ("Incident Procedures", _count(docs.get("incident_procedures")), "neutral"),
                ("Rollback Guides", _count(docs.get("rollback_instructions")), "neutral"),
                ("Options Income Docs", _count(docs.get("options_income_documentation")), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Documentation operational coverage",
        )
        + '<div class="mc-operator-stack">'
        + '<div class="mc-section-anchor" id="mc-docs-coverage">'
        + detail_table("Documentation Coverage Snapshot", {
            "architecture": _count(docs.get("architecture")),
            "governance": _count(docs.get("governance")),
            "release_reports": _count(docs.get("release_reports")),
            "certification_reports": _count(docs.get("certification_reports")),
            "rc1_validation_reports": _count(docs.get("rc1_validation_reports")),
        })
        + '</div>'
        + '<div class="mc-section-anchor" id="mc-docs-ops">'
        + detail_table("Operational Runbook Snapshot", {
            "operator_runbooks": _count(docs.get("operator_runbooks")),
            "rollback_instructions": _count(docs.get("rollback_instructions")),
            "broker_onboarding_guides": _count(docs.get("broker_onboarding_guides")),
            "incident_procedures": _count(docs.get("incident_procedures")),
            "options_income_documentation": _count(docs.get("options_income_documentation")),
            "browser_paths_expose_absolute_paths": docs.get("browser_paths_expose_absolute_paths"),
        })
        + '</div>'
        + _evidence_panel("mc-docs-evidence", "Show architecture and governance document index", detail_table("Architecture And Governance", {
            "architecture": docs.get("architecture"),
            "governance": docs.get("governance"),
            "release_reports": docs.get("release_reports"),
            "certification_reports": docs.get("certification_reports"),
        }))
        + _evidence_panel("mc-docs-runbooks", "Show full operational runbook index", detail_table("Operational Runbooks", {
            "operator_runbooks": docs.get("operator_runbooks"),
            "rollback_instructions": docs.get("rollback_instructions"),
            "broker_onboarding_guides": docs.get("broker_onboarding_guides"),
            "incident_procedures": docs.get("incident_procedures"),
            "rc1_validation_reports": docs.get("rc1_validation_reports"),
            "options_income_documentation": docs.get("options_income_documentation"),
            "browser_paths_expose_absolute_paths": docs.get("browser_paths_expose_absolute_paths"),
        }))
        + '</div>'
    )
