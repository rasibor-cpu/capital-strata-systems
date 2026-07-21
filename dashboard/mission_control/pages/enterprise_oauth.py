"""Read-only Enterprise OAuth governance page."""

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
    data = redact_value(raw if isinstance(raw, dict) else {})
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
        + metric_grid(
            (
                ("Providers", len(providers), "neutral"),
                ("Registrations", len(authorization), "neutral"),
                ("High Risk", risk.get("high_risk_count", 0), "warning"),
                ("Certification", certification.get("outcome", "NOT_CERTIFIED"), certification.get("outcome", "neutral")),
                ("Execution", "BLOCKED", "blocked"),
            )
        )
        + split_panels(
            detail_table("Provider Inventory", providers),
            detail_table("Authorization Status", authorization),
            detail_table("Scope Summary", scopes),
            detail_table("Expiry Forecast", expiry),
            detail_table("Rotation Readiness", rotation),
            detail_table("Risk", risk),
            detail_table("Policy", policy),
            detail_table("Audit", audit),
        )
    )


__all__ = ["render"]
