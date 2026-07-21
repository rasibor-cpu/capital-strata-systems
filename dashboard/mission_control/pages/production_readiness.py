"""Read-only Production Readiness executive dashboard."""

from __future__ import annotations

from backend.security.vault_redaction import redact_value
from dashboard.mission_control.pages._components import (
    detail_table,
    metric_grid,
    page_header,
    split_panels,
    warning_banner,
)


def render(state: dict) -> str:
    auth = (
        state.get("authorization_context")
        if isinstance(state.get("authorization_context"), dict)
        else {}
    )
    if not (
        auth.get("authenticated")
        and auth.get("active")
        and str(auth.get("role") or "").upper() in {"SUPER_USER", "ADMIN"}
    ):
        return (
            page_header(
                "Production Readiness",
                "Controlled-deployment certification evidence.",
            )
            + warning_banner("Administrator authentication is required.")
        )
    source = state.get("production_readiness")
    data = redact_value(source if isinstance(source, dict) else {})
    return (
        page_header(
            "Production Readiness",
            "Operational acceptance, endurance, recovery, deployment, and certification evidence.",
        )
        + warning_banner(
            "Certification readiness does not authorize deployment, trading, or execution.",
            status="warn",
        )
        + metric_grid(
            (
                (
                    "Certification Score",
                    f"{data.get('certification_score', 0)}%",
                    data.get("status"),
                ),
                (
                    "Governance Score",
                    f"{data.get('governance_score', 0)}%",
                    "neutral",
                ),
                ("Broker Readiness", data.get("broker_readiness"), data.get("broker_readiness")),
                ("Runtime Readiness", data.get("runtime_readiness"), data.get("runtime_readiness")),
                (
                    "Evidence Completeness",
                    f"{data.get('evidence_completeness', 0)}%",
                    "neutral",
                ),
                (
                    "Deployment Blockers",
                    len(data.get("deployment_blockers", [])),
                    "warning",
                ),
                (
                    "Outstanding Risks",
                    data.get("outstanding_risks", {}).get("unmitigated_count", 0)
                    if isinstance(data.get("outstanding_risks"), dict)
                    else 0,
                    "warning",
                ),
                ("Execution", "BLOCKED", "blocked"),
            )
        )
        + split_panels(
            detail_table("Platform Certification", data.get("platform_certification", {})),
            detail_table("Operational Acceptance", data.get("operational_acceptance", {})),
            detail_table("Endurance Readiness", data.get("endurance_readiness", {})),
            detail_table(
                "Disaster Recovery Readiness",
                data.get("disaster_recovery_readiness", {}),
            ),
            detail_table("Deployment Readiness", data.get("deployment_readiness", {})),
            detail_table(
                "Deployment Blockers",
                {"blockers": data.get("deployment_blockers", [])},
            ),
            detail_table("Outstanding Risks", data.get("outstanding_risks", {})),
            detail_table(
                "Evidence Completeness",
                {
                    "percentage": data.get("evidence_completeness"),
                    "evidence_fabricated": data.get("evidence_fabricated"),
                    "deployment_authorized": data.get("deployment_authorized"),
                },
            ),
        )
    )


__all__ = ["render"]
