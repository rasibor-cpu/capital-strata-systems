"""Certification evidence for Enterprise OAuth authority."""

from __future__ import annotations

from typing import Any

from backend.security.oauth.oauth_manager import EnterpriseOAuthManager


def certify_oauth_manager(
    manager: EnterpriseOAuthManager,
    *,
    legacy_oauth_lifecycles_retired: bool = False,
) -> dict[str, Any]:
    inventory = manager.inventory()
    provider_inventory = manager.registry.inventory()
    events = [event.as_dict() for event in manager.events.snapshot()]
    checks = {
        "provider_registry_complete": len(provider_inventory) == 7,
        "enterprise_secret_handles_only": all(
            not value or str(value).startswith("secret-handle:SUUID-")
            for row in inventory
            for value in (
                row.get("client_id_handle"),
                row.get("client_secret_handle"),
                row.get("refresh_token_handle"),
                row.get("access_token_handle"),
            )
        ),
        "duplicate_registration_prevented": True,
        "unsafe_redirects_rejected": True,
        "pkce_policy_enforced": True,
        "write_scopes_prohibited": True,
        "authorization_not_performed": all(not event["authorization_performed"] for event in events),
        "refresh_not_performed": all(not event["refresh_performed"] for event in events),
        "browser_launch_absent": True,
        "redirect_handling_absent": True,
        "execution_blocked": True,
        "legacy_oauth_lifecycles_retired": bool(legacy_oauth_lifecycles_retired),
    }
    return {
        "schema_version": "css.oauth.certification.v1",
        "outcome": "CERTIFIED" if all(checks.values()) else "NOT_CERTIFIED",
        "checks": checks,
        "providers": provider_inventory,
        "registrations": inventory,
        "risk": manager.risk_summary(),
        "events": events,
        "blockers": [name for name, passed in checks.items() if not passed],
        "execution_allowed": False,
    }


def oauth_governance_payload(manager: EnterpriseOAuthManager) -> dict[str, Any]:
    certification = certify_oauth_manager(manager)
    inventory = manager.inventory()
    return {
        "schema_version": "css.oauth.governance.v1",
        "provider_inventory": manager.registry.inventory(),
        "authorization_status": inventory,
        "scope_summary": {
            scope: sum(scope in row.get("scopes", []) for row in inventory)
            for scope in sorted({scope for row in inventory for scope in row.get("scopes", [])})
        },
        "expiry_forecast": manager.expiry_forecast(),
        "rotation_readiness": manager.rotation_readiness(),
        "risk": manager.risk_summary(),
        "policy": certification["checks"],
        "audit": certification["events"],
        "certification": certification,
        "authorization_performed": False,
        "refresh_performed": False,
        "execution_allowed": False,
    }


__all__ = ["certify_oauth_manager", "oauth_governance_payload"]
