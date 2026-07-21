"""Enterprise A4 OAuth governance reports."""

from __future__ import annotations

from typing import Any
import uuid

from backend.broker_reporting.page_layout import build_paginated_document
from backend.security.oauth.oauth_certification import certify_oauth_manager
from backend.security.oauth.oauth_manager import EnterpriseOAuthManager
from backend.security.oauth.oauth_models import utc_now

OAUTH_REPORT_TITLES = {
    "oauth_certification": "Enterprise OAuth Certification",
    "provider_inventory": "OAuth Provider Inventory",
    "authorization_readiness": "OAuth Authorization Readiness",
    "token_lifecycle": "OAuth Token Lifecycle",
    "rotation_forecast": "OAuth Rotation Forecast",
    "policy_compliance": "OAuth Policy Compliance",
}


def build_oauth_report(
    report_type: str,
    *,
    manager: EnterpriseOAuthManager,
) -> dict[str, Any]:
    key = str(report_type).lower()
    if key not in OAUTH_REPORT_TITLES:
        raise KeyError("OAUTH_REPORT_TYPE_UNKNOWN")
    certification = certify_oauth_manager(manager)
    sections = {
        "oauth_certification": [
            ("Certification", certification),
            ("Risk", manager.risk_summary()),
        ],
        "provider_inventory": [
            ("Provider Registry", manager.registry.inventory()),
            ("Registrations", manager.inventory()),
        ],
        "authorization_readiness": [
            ("Authorization Status", manager.inventory()),
            ("Scope Summary", _scope_summary(manager.inventory())),
        ],
        "token_lifecycle": [
            ("Lifecycle", manager.inventory()),
            ("Expiry Forecast", manager.expiry_forecast()),
        ],
        "rotation_forecast": [
            ("Rotation Readiness", manager.rotation_readiness()),
            ("Expiry Forecast", manager.expiry_forecast()),
        ],
        "policy_compliance": [
            ("Policy Checks", certification["checks"]),
            ("Audit Events", certification["events"]),
        ],
    }[key]
    generated = utc_now()
    report_id = f"OAUTH-{key.upper()}-{uuid.uuid4().hex[:10].upper()}"
    document = build_paginated_document(
        title=OAUTH_REPORT_TITLES[key],
        report_id=report_id,
        css_version="Phase-179B",
        commit_reference=None,
        generated_at=generated,
        executive_summary=[
            f"Certification outcome: {certification['outcome']}",
            f"Providers: {len(certification['providers'])}",
            f"Registrations: {len(certification['registrations'])}",
            "Authorization performed: false",
            "Token refresh performed: false",
            "Execution authority: BLOCKED",
        ],
        sections=sections,
    )
    return {
        "schema_version": "css.oauth.report.v1",
        "report_type": key,
        "report_id": report_id,
        "generated_at": generated,
        "document": document.as_dict(),
        "viewer_compatible": True,
        "execution_allowed": False,
    }


def build_oauth_report_suite(manager: EnterpriseOAuthManager) -> dict[str, dict[str, Any]]:
    return {
        report_type: build_oauth_report(report_type, manager=manager)
        for report_type in OAUTH_REPORT_TITLES
    }


def _scope_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        for scope in row.get("scopes", []):
            summary[str(scope)] = summary.get(str(scope), 0) + 1
    return summary


__all__ = ["OAUTH_REPORT_TITLES", "build_oauth_report", "build_oauth_report_suite"]
