"""Offline OAuth metadata discovery and registration."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.security.oauth.oauth_manager import DuplicateOAuthRegistration, EnterpriseOAuthManager
from backend.security.oauth.oauth_models import OAuthProvider, OAuthTokenType


class OAuthDiscovery:
    def __init__(self, manager: EnterpriseOAuthManager):
        self.manager = manager

    def discover(self, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        results = []
        for entry in entries:
            provider_value = str(entry.get("provider") or "").upper()
            issues: list[str] = []
            try:
                provider = OAuthProvider(provider_value)
            except ValueError:
                results.append(
                    {
                        "provider": provider_value or "UNKNOWN",
                        "registered": False,
                        "issues": ["PROVIDER_NOT_SUPPORTED"],
                    }
                )
                continue
            scopes = tuple(str(scope) for scope in entry.get("scopes", ()) if str(scope))
            definition = self.manager.registry.get(provider)
            if set(scopes) - set(definition.allowed_scopes):
                issues.append("SCOPE_MISMATCH")
            if definition.pkce_required and not bool(entry.get("pkce_configured")):
                issues.append("PKCE_REQUIRED")
            redirect = str(entry.get("redirect_uri") or "") or None
            try:
                registration = self.manager.register(
                    provider=provider,
                    environment=str(entry.get("environment") or "UNCONFIGURED"),
                    owner=str(entry.get("owner") or "UNASSIGNED"),
                    scopes=scopes,
                    token_type=OAuthTokenType(
                        str(entry.get("token_type") or "AUTHORIZATION_CODE").upper()
                    ),
                    client_id_secret_uuid=entry.get("client_id_secret_uuid"),
                    client_secret_uuid=entry.get("client_secret_uuid"),
                    refresh_token_uuid=entry.get("refresh_token_uuid"),
                    access_token_uuid=entry.get("access_token_uuid"),
                    redirect_uri=redirect,
                    pkce_configured=bool(entry.get("pkce_configured")),
                    expiry=entry.get("expiry"),
                )
                results.append(
                    {
                        "provider": provider.value,
                        "oauth_id": registration.oauth_id,
                        "registered": True,
                        "status": registration.status.value,
                        "issues": sorted(set(issues)),
                    }
                )
            except DuplicateOAuthRegistration:
                results.append(
                    {
                        "provider": provider.value,
                        "registered": False,
                        "duplicate": True,
                        "issues": ["DUPLICATE_REGISTRATION"],
                    }
                )
            except (ValueError, KeyError) as exc:
                code = str(exc).split(":", 1)[-1]
                results.append(
                    {
                        "provider": provider.value,
                        "registered": False,
                        "issues": sorted(set([*issues, code])),
                    }
                )
        return {
            "schema_version": "css.oauth.discovery.v1",
            "results": results,
            "live_validation_performed": False,
            "authorization_performed": False,
            "refresh_performed": False,
            "execution_allowed": False,
        }


__all__ = ["OAuthDiscovery"]
