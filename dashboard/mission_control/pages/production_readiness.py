"""Read-only Production Readiness executive dashboard."""

from __future__ import annotations

from backend.security.vault_redaction import redact_value
from dashboard.mission_control.pages._components import (
    detail_table,
    metric_grid,
    page_header,
    warning_banner,
)


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
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
        + '<nav class="mc-page-jump" aria-label="Production Readiness sections">'
          '<a href="#mc-prod-status">Status</a>'
          '<a href="#mc-prod-blockers">Blockers</a>'
          '<a href="#mc-prod-risk">Risks</a>'
          '<a href="#mc-prod-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Certification Score", f"{data.get('certification_score', 0)}%", data.get("status")),
                ("Broker Readiness", data.get("broker_readiness"), data.get("broker_readiness")),
                ("Runtime Readiness", data.get("runtime_readiness"), data.get("runtime_readiness")),
                ("Execution", "BLOCKED", "blocked"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-prod-priority",
            aria_label="Production Readiness priority",
        )
        + metric_grid(
            (
                ("Governance Score", f"{data.get('governance_score', 0)}%", "neutral"),
                ("Evidence Completeness", f"{data.get('evidence_completeness', 0)}%", "neutral"),
                ("Deployment Blockers", len(data.get("deployment_blockers", [])), "warning"),
                (
                    "Outstanding Risks",
                    data.get("outstanding_risks", {}).get("unmitigated_count", 0)
                    if isinstance(data.get("outstanding_risks"), dict)
                    else 0,
                    "warning",
                ),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Production Readiness secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-prod-status", detail_table("Readiness Snapshot", {
            "status": data.get("status"),
            "certification_score": data.get("certification_score"),
            "governance_score": data.get("governance_score"),
            "broker_readiness": data.get("broker_readiness"),
            "runtime_readiness": data.get("runtime_readiness"),
            "deployment_authorized": data.get("deployment_authorized"),
        }))
        + _anchor_panel("mc-prod-blockers", detail_table("Deployment Blockers", {
            "blocker_count": len(data.get("deployment_blockers", [])),
            "blockers": data.get("deployment_blockers", []),
        }))
        + _anchor_panel("mc-prod-risk", detail_table("Outstanding Risks", data.get("outstanding_risks", {})))
        + _anchor_panel("mc-prod-evidence", detail_table("Evidence Completeness", {
            "percentage": data.get("evidence_completeness"),
            "evidence_fabricated": data.get("evidence_fabricated"),
            "deployment_authorized": data.get("deployment_authorized"),
        }))
        + _evidence_panel("mc-prod-platform", "Show platform certification evidence", detail_table("Platform Certification", data.get("platform_certification", {})))
        + _evidence_panel("mc-prod-operational", "Show operational acceptance evidence", detail_table("Operational Acceptance", data.get("operational_acceptance", {})))
        + _evidence_panel("mc-prod-endurance", "Show endurance evidence", detail_table("Endurance Readiness", data.get("endurance_readiness", {})))
        + _evidence_panel("mc-prod-dr", "Show disaster-recovery evidence", detail_table("Disaster Recovery Readiness", data.get("disaster_recovery_readiness", {})))
        + _evidence_panel("mc-prod-deployment", "Show deployment-readiness evidence", detail_table("Deployment Readiness", data.get("deployment_readiness", {})))
        + '</div>'
    )


__all__ = ["render"]
