"""Read-only Enterprise OAuth governance page."""

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


def _count(value: object) -> object:
    if isinstance(value, (list, dict, tuple, set)):
        return len(value)
    return "EVIDENCE_MISSING"


def _source_count(source: dict, key: str) -> object:
    if key not in source:
        return "EVIDENCE_MISSING"
    return _count(source.get(key))


def _risk_status(risk: dict, key: str) -> str:
    if key not in risk:
        return "EVIDENCE_MISSING"
    value = risk.get(key)
    try:
        count = int(value)
    except (TypeError, ValueError):
        return "EVIDENCE_MISSING"
    return "PASS" if count == 0 else "WARNING"


def render(state: dict) -> str:
    auth = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    if not (
        auth.get("authenticated")
        and auth.get("active")
        and str(auth.get("role") or "").upper() in {"SUPER_USER", "ADMIN"}
    ):
        return (
            page_header("Enterprise OAuth", "Provider-neutral OAuth governance metadata.")
            + warning_banner("Administrator authentication is required.")
        )
    raw = state.get("oauth_governance")
    source = raw if isinstance(raw, dict) else {}
    data = redact_value(source)
    providers = data.get("provider_inventory") if isinstance(data.get("provider_inventory"), list) else []
    authorization = data.get("authorization_status") if isinstance(data.get("authorization_status"), list) else []
    scopes = data.get("scope_summary") if isinstance(data.get("scope_summary"), dict) else {}
    expiry = data.get("expiry_forecast") if isinstance(data.get("expiry_forecast"), list) else []
    rotation = data.get("rotation_readiness") if isinstance(data.get("rotation_readiness"), dict) else {}
    risk = data.get("risk") if isinstance(data.get("risk"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    audit = data.get("audit") if isinstance(data.get("audit"), list) else []
    certification = data.get("certification") if isinstance(data.get("certification"), dict) else {}
    return (
        page_header(
            "Enterprise OAuth",
            "Registration-only OAuth authority. No authorization, refresh, redirect handling, browser launch, or execution.",
        )
        + '<nav class="mc-page-jump" aria-label="Enterprise OAuth sections">'
          '<a href="#mc-oauth-status">Status</a>'
          '<a href="#mc-oauth-risk">Risk</a>'
          '<a href="#mc-oauth-policy">Policy</a>'
          '<a href="#mc-oauth-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Providers", _source_count(source, "provider_inventory"), _source_count(source, "provider_inventory")),
                ("Registrations", _source_count(source, "authorization_status"), _source_count(source, "authorization_status")),
                ("Certification", certification.get("outcome", "NOT_CERTIFIED"), certification.get("outcome", "NOT_CERTIFIED")),
                ("Execution", "BLOCKED", "blocked"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-oauth-priority",
            aria_label="Enterprise OAuth priority",
        )
        + metric_grid(
            (
                ("High Risk", risk.get("high_risk_count", "EVIDENCE_MISSING"), _risk_status(risk, "high_risk_count")),
                ("Expiry Forecast", _source_count(source, "expiry_forecast"), _source_count(source, "expiry_forecast")),
                ("Audit Events", _source_count(source, "audit"), _source_count(source, "audit")),
                ("Scope Groups", _source_count(source, "scope_summary"), _source_count(source, "scope_summary")),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Enterprise OAuth secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-oauth-status", detail_table("OAuth Governance Snapshot", {
            "provider_count": _source_count(source, "provider_inventory"),
            "registration_count": _source_count(source, "authorization_status"),
            "certification": certification.get("outcome", "NOT_CERTIFIED"),
            "execution": "BLOCKED",
        }))
        + _anchor_panel("mc-oauth-risk", detail_table("OAuth Risk Snapshot", {
            "high_risk_count": risk.get("high_risk_count", "EVIDENCE_MISSING"),
            "expiry_forecast_count": _source_count(source, "expiry_forecast"),
            "audit_event_count": _source_count(source, "audit"),
            "rotation_readiness": rotation.get("status", rotation.get("outcome", "EVIDENCE_MISSING")),
        }))
        + _anchor_panel("mc-oauth-policy", detail_table("OAuth Policy Snapshot", {
            "policy_status": policy.get("status", policy.get("outcome", "EVIDENCE_MISSING")),
            "scope_group_count": _source_count(source, "scope_summary"),
            "authorization_flow_enabled": "DISABLED",
            "refresh_flow_enabled": "DISABLED",
            "browser_launch_enabled": "DISABLED",
        }))
        + _evidence_panel("mc-oauth-evidence", "Show provider and registration metadata", detail_table("Provider Inventory", providers) + detail_table("Authorization Status", authorization))
        + _evidence_panel("mc-oauth-scope", "Show scope and expiry metadata", detail_table("Scope Summary", scopes) + detail_table("Expiry Forecast", expiry))
        + _evidence_panel("mc-oauth-rotation", "Show rotation and risk metadata", detail_table("Rotation Readiness", rotation) + detail_table("Risk", risk))
        + _evidence_panel("mc-oauth-governance", "Show policy and audit metadata", detail_table("Policy", policy) + detail_table("Audit", audit))
        + '</div>'
    )


__all__ = ["render"]
