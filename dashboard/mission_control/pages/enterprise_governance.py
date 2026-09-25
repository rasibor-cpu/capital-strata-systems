"""Administrative read-only Enterprise Governance dashboard."""

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


def _count(value: object, *, missing: str = "EVIDENCE_MISSING") -> object:
    if isinstance(value, list):
        return len(value)
    return missing


def _score_status(value: object) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "EVIDENCE_MISSING"
    if score <= 0:
        return "EVIDENCE_MISSING"
    if score < 100:
        return "WARNING"
    return "PASS"


def _risk_count(risk: dict, key: str) -> object:
    if key not in risk:
        return "EVIDENCE_MISSING"
    value = risk.get(key)
    return "EVIDENCE_MISSING" if value in (None, "") else value


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
        + '<nav class="mc-page-jump" aria-label="Executive Governance sections">'
          '<a href="#mc-gov-status">Status</a>'
          '<a href="#mc-gov-risk">Risk</a>'
          '<a href="#mc-gov-blockers">Blockers</a>'
          '<a href="#mc-gov-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Overall Readiness", f"{data.get('overall_certification_readiness', 0)}%", _score_status(data.get("overall_certification_readiness"))),
                ("Broker Readiness", data.get("broker_readiness"), data.get("broker_readiness")),
                ("Runtime Readiness", data.get("runtime_readiness"), data.get("runtime_readiness")),
                ("Execution", "BLOCKED", "blocked"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-gov-priority",
            aria_label="Executive Governance priority",
        )
        + metric_grid(
            (
                ("Governance Score", f"{data.get('governance_score', 0)}%", _score_status(data.get("governance_score"))),
                ("ISO 27001", f"{iso27001.get('percentage', 0)}%", _score_status(iso27001.get("percentage"))),
                ("ISO 9001", f"{iso9001.get('percentage', 0)}%", _score_status(iso9001.get("percentage"))),
                ("Critical Risks", _risk_count(risk, "critical_count"), _risk_count(risk, "critical_count")),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Executive Governance secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-gov-status", detail_table("Governance Snapshot", {
            "security_posture": data.get("security_posture"),
            "compliance_posture": data.get("compliance_posture"),
            "governance_score": data.get("governance_score"),
            "overall_certification_readiness": data.get("overall_certification_readiness"),
            "broker_readiness": data.get("broker_readiness"),
            "runtime_readiness": data.get("runtime_readiness"),
        }))
        + _anchor_panel("mc-gov-risk", detail_table("Enterprise Risk Snapshot", {
            "critical_count": _risk_count(risk, "critical_count"),
            "high_count": _risk_count(risk, "high_count"),
            "medium_count": _risk_count(risk, "medium_count"),
            "low_count": _risk_count(risk, "low_count"),
            "risk_register_count": _count(data.get("enterprise_risk_register")),
        }))
        + _anchor_panel("mc-gov-blockers", detail_table("Certification Blockers Snapshot — Outstanding Certification Blockers", {
            "blocker_count": _count(data.get("outstanding_blockers")),
            "blockers": data.get("outstanding_blockers", "EVIDENCE_MISSING"),
        }))
        + _evidence_panel("mc-gov-evidence", "Show governance-domain evidence", detail_table("Governance Domains", data.get("domains", {})))
        + _evidence_panel("mc-gov-iso", "Show ISO readiness evidence", detail_table("ISO 27001 Readiness", iso27001) + detail_table("ISO 9001 Readiness", iso9001))
        + _evidence_panel("mc-gov-continuity", "Show continuity and risk evidence", detail_table("Business Continuity", continuity) + detail_table("Enterprise Risk Summary", risk) + detail_table("Enterprise Risk Register", data.get("enterprise_risk_register", [])))
        + _evidence_panel("mc-gov-certification", "Show certification evidence", detail_table("Certification Evidence", certification))
        + '</div>'
    )


__all__ = ["render"]
