"""Fail-closed OAuth registration and state-transition policy."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from urllib.parse import urlsplit

from backend.security.oauth.oauth_models import OAuthRegistration, OAuthStatus
from backend.security.oauth.oauth_registry import OAuthProviderDefinition


@dataclass(frozen=True)
class OAuthPolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]


_TRANSITIONS = {
    OAuthStatus.UNCONFIGURED: {
        OAuthStatus.REGISTERED,
        OAuthStatus.CONFIGURATION_REQUIRED,
        OAuthStatus.DISABLED,
    },
    OAuthStatus.REGISTERED: {
        OAuthStatus.CONFIGURATION_REQUIRED,
        OAuthStatus.AUTHORIZATION_PENDING,
        OAuthStatus.DISABLED,
        OAuthStatus.FAILED,
    },
    OAuthStatus.CONFIGURATION_REQUIRED: {
        OAuthStatus.REGISTERED,
        OAuthStatus.DISABLED,
        OAuthStatus.FAILED,
    },
    OAuthStatus.AUTHORIZATION_PENDING: {OAuthStatus.DISABLED, OAuthStatus.FAILED},
    OAuthStatus.AUTHORIZED: {
        OAuthStatus.TOKEN_EXPIRED,
        OAuthStatus.TOKEN_REVOKED,
        OAuthStatus.ROTATION_REQUIRED,
        OAuthStatus.DISABLED,
    },
    OAuthStatus.TOKEN_EXPIRED: {OAuthStatus.ROTATION_REQUIRED, OAuthStatus.DISABLED},
    OAuthStatus.TOKEN_REVOKED: {OAuthStatus.DISABLED},
    OAuthStatus.ROTATION_REQUIRED: {OAuthStatus.DISABLED, OAuthStatus.FAILED},
    OAuthStatus.DISABLED: {OAuthStatus.REGISTERED},
    OAuthStatus.FAILED: {OAuthStatus.CONFIGURATION_REQUIRED, OAuthStatus.DISABLED},
}


class OAuthPolicy:
    def validate_registration(
        self,
        registration: OAuthRegistration,
        definition: OAuthProviderDefinition,
    ) -> OAuthPolicyDecision:
        reasons: list[str] = []
        if not registration.owner.strip() or not registration.environment.strip():
            reasons.append("OWNER_AND_ENVIRONMENT_REQUIRED")
        if registration.redirect_uri and not _safe_redirect_uri(registration.redirect_uri):
            reasons.append("UNSAFE_REDIRECT_URI")
        if (
            registration.token_type.value == "AUTHORIZATION_CODE"
            and not registration.redirect_uri
        ):
            reasons.append("REDIRECT_URI_REQUIRED")
        if definition.pkce_required and not registration.pkce_configured:
            reasons.append("PKCE_REQUIRED")
        unsupported = set(registration.scopes) - set(definition.allowed_scopes)
        if unsupported:
            reasons.append("SCOPE_MISMATCH")
        if any(token in scope.lower() for scope in registration.scopes for token in ("write", "trade", "order")):
            reasons.append("WRITE_SCOPE_PROHIBITED")
        handles = (
            registration.client_id_handle,
            registration.client_secret_handle,
            registration.refresh_token_handle,
            registration.access_token_handle,
        )
        if any(value and not str(value).startswith("secret-handle:SUUID-") for value in handles):
            reasons.append("NON_ENTERPRISE_SECRET_REFERENCE")
        return OAuthPolicyDecision(not reasons, tuple(reasons))

    def validate_transition(
        self,
        current: OAuthStatus,
        target: OAuthStatus,
    ) -> OAuthPolicyDecision:
        if target is OAuthStatus.AUTHORIZED:
            return OAuthPolicyDecision(False, ("LIVE_AUTHORIZATION_PROHIBITED",))
        if target not in _TRANSITIONS.get(current, set()):
            return OAuthPolicyDecision(False, ("OAUTH_TRANSITION_PROHIBITED",))
        return OAuthPolicyDecision(True, ())


def _safe_redirect_uri(value: str) -> bool:
    try:
        parsed = urlsplit(str(value))
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.fragment or parsed.query:
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"}:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        return True
    except Exception:
        return False


__all__ = ["OAuthPolicy", "OAuthPolicyDecision"]
