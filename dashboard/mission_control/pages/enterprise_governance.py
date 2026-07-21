"""Administrative read-only Enterprise Governance dashboard."""

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
                "Executive Governance",
                "Enterprise governance and formal-certification readiness.",
            )
            + warning_banner("Administrator authentication is required.")
        )
    source = state.get("enterprise_governance")
    data = redact_value(source if isinstance(source, dict) else {})
    iso27001 = data.get("iso_27001") if isinstance(data.get("iso_27001"), dict) else {}
    iso9001 = data.get("iso_9001") if isinstance(data.get("iso_9001"), dict) else {}
    continuity = (
        data.get("business_continuity")
        if isinstance(data.get("business_continuity"), dict)
        else {}
    )
    risk = (
        data.get("enterprise_risk_summary")
        if isinstance(data.get("enterprise_risk_summary"), dict)
        else {}
    )
    certification = (
        data.get("certification")
        if isinstance(data.get("certification"), dict)
        else {}
    )
    return (
        page_header(
            "Executive Governance",
            "Read-only governance, ISO readiness, continuity, risk, compliance, and certification evidence.",
        )
        + warning_banner(
            "Readiness evidence is not ISO certification or production authorization.",
            status="warn",
        )
        + metric_grid(
            (
                (
                    "Overall Readiness",
                    f"{data.get('overall_certification_readiness', 0)}%",
                    "neutral",
                ),
                (
                    "Governance Score",
                    f"{data.get('governance_score', 0)}%",
                    "neutral",
                ),
                ("ISO 27001", f"{iso27001.get('percentage', 0)}%", "neutral"),
                ("ISO 9001", f"{iso9001.get('percentage', 0)}%", "neutral"),
                ("Broker Readiness", data.get("broker_readiness"), data.get("broker_readiness")),
                ("Runtime Readiness", data.get("runtime_readiness"), data.get("runtime_readiness")),
                ("Security", data.get("security_posture"), data.get("security_posture")),
                ("Compliance", data.get("compliance_posture"), data.get("compliance_posture")),
                ("Critical Risks", risk.get("critical_count", 0), "warning"),
                ("Execution", "BLOCKED", "blocked"),
            )
        )
        + split_panels(
            detail_table("Governance Domains", data.get("domains", {})),
            detail_table("ISO 27001 Readiness", iso27001),
            detail_table("ISO 9001 Readiness", iso9001),
            detail_table("Business Continuity", continuity),
            detail_table("Enterprise Risk Summary", risk),
            detail_table(
                "Enterprise Risk Register",
                data.get("enterprise_risk_register", []),
            ),
            detail_table("Certification Evidence", certification),
            detail_table(
                "Outstanding Certification Blockers",
                {"blockers": data.get("outstanding_blockers", [])},
            ),
        )
    )


__all__ = ["render"]
