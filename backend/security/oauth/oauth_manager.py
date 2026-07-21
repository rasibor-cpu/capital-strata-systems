"""Enterprise OAuth authority — registration and metadata only."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import threading
import uuid
from typing import Any

from backend.security.identity.enterprise_secret_service import EnterpriseSecretService
from backend.security.oauth.oauth_events import OAuthEventStream
from backend.security.oauth.oauth_handles import issue_oauth_handle
from backend.security.oauth.oauth_models import (
    OAuthProvider,
    OAuthRegistration,
    OAuthStatus,
    OAuthTokenType,
    utc_now,
)
from backend.security.oauth.oauth_policy import OAuthPolicy
from backend.security.oauth.oauth_registry import OAuthProviderRegistry


class DuplicateOAuthRegistration(ValueError):
    pass


class OAuthManager:
    def __init__(
        self,
        *,
        secrets: EnterpriseSecretService,
        registry: OAuthProviderRegistry | None = None,
        policy: OAuthPolicy | None = None,
        events: OAuthEventStream | None = None,
    ):
        self.secrets = secrets
        self.registry = registry or OAuthProviderRegistry()
        self.policy = policy or OAuthPolicy()
        self.events = events or OAuthEventStream()
        self._registrations: dict[str, OAuthRegistration] = {}
        self._keys: dict[tuple[str, str, str], str] = {}
        self._lock = threading.RLock()

    def register(
        self,
        *,
        provider: OAuthProvider | str,
        environment: str,
        owner: str,
        scopes: tuple[str, ...] = (),
        token_type: OAuthTokenType = OAuthTokenType.AUTHORIZATION_CODE,
        client_id_secret_uuid: str | None = None,
        client_secret_uuid: str | None = None,
        refresh_token_uuid: str | None = None,
        access_token_uuid: str | None = None,
        redirect_uri: str | None = None,
        pkce_configured: bool = False,
        expiry: str | None = None,
    ) -> OAuthRegistration:
        definition = self.registry.get(provider)
        key = (definition.provider.value, str(environment).upper(), str(owner))
        with self._lock:
            duplicate = self._keys.get(key)
            if duplicate:
                raise DuplicateOAuthRegistration(f"DUPLICATE_OAUTH_REGISTRATION:{duplicate}")
        references = {
            "client_id_handle": self._secret_reference(client_id_secret_uuid),
            "client_secret_handle": self._secret_reference(client_secret_uuid),
            "refresh_token_handle": self._secret_reference(refresh_token_uuid),
            "access_token_handle": self._secret_reference(access_token_uuid),
        }
        configured = bool(references["client_id_handle"]) and (
            not definition.pkce_required or pkce_configured
        ) and (token_type is not OAuthTokenType.AUTHORIZATION_CODE or bool(redirect_uri))
        status = OAuthStatus.REGISTERED if configured else OAuthStatus.CONFIGURATION_REQUIRED
        oauth_id = f"OID-{uuid.uuid4()}"
        correlation_id = str(uuid.uuid4())
        registration = OAuthRegistration(
            oauth_id=oauth_id,
            provider=definition.provider,
            environment=str(environment).upper(),
            owner=str(owner),
            scopes=tuple(sorted(set(str(scope) for scope in scopes if str(scope)))),
            token_type=token_type,
            status=status,
            issued=utc_now(),
            expiry=expiry,
            refresh_capability=bool(definition.refresh_supported and references["refresh_token_handle"]),
            correlation_id=correlation_id,
            redirect_uri=str(redirect_uri) if redirect_uri else None,
            pkce_required=definition.pkce_required,
            pkce_configured=bool(pkce_configured),
            risk_score=0,
            **references,
        )
        decision = self.policy.validate_registration(registration, definition)
        fatal = set(decision.reasons) - {"PKCE_REQUIRED", "REDIRECT_URI_REQUIRED"}
        if fatal:
            self.events.publish(
                oauth_id=oauth_id,
                provider=definition.provider.value,
                action="REGISTER",
                result="DENIED",
                reason="|".join(fatal),
                correlation_id=correlation_id,
            )
            raise ValueError(f"OAUTH_REGISTRATION_REJECTED:{'|'.join(sorted(fatal))}")
        registration = replace(registration, risk_score=self._risk_score(registration))
        with self._lock:
            duplicate = self._keys.get(key)
            if duplicate:
                raise DuplicateOAuthRegistration(f"DUPLICATE_OAUTH_REGISTRATION:{duplicate}")
            self._registrations[oauth_id] = registration
            self._keys[key] = oauth_id
        self.events.publish(
            oauth_id=oauth_id,
            provider=definition.provider.value,
            action="REGISTER",
            result="SUCCESS",
            reason=status.value,
            correlation_id=correlation_id,
        )
        return registration

    def transition(self, oauth_id: str, target: OAuthStatus, *, reason: str) -> OAuthRegistration:
        current = self.get(oauth_id)
        decision = self.policy.validate_transition(current.status, target)
        if not decision.allowed:
            self.events.publish(
                oauth_id=oauth_id,
                provider=current.provider.value,
                action="TRANSITION",
                result="DENIED",
                reason="|".join(decision.reasons),
                correlation_id=current.correlation_id,
            )
            raise PermissionError("|".join(decision.reasons))
        validation = {
            "timestamp": utc_now(),
            "from": current.status.value,
            "to": target.value,
            "reason": str(reason).upper(),
            "live_operation": False,
        }
        updated = replace(
            current,
            status=target,
            disabled=target is OAuthStatus.DISABLED,
            risk_score=self._risk_score(replace(current, status=target)),
            validation_history=(*current.validation_history, validation)[-25:],
        )
        with self._lock:
            self._registrations[oauth_id] = updated
        self.events.publish(
            oauth_id=oauth_id,
            provider=current.provider.value,
            action="TRANSITION",
            result="SUCCESS",
            reason=reason,
            correlation_id=current.correlation_id,
        )
        return updated

    def get(self, oauth_id: str) -> OAuthRegistration:
        with self._lock:
            registration = self._registrations.get(str(oauth_id))
        if registration is None:
            raise KeyError("OAUTH_REGISTRATION_NOT_FOUND")
        return registration

    def get_provider(self, provider: OAuthProvider | str) -> list[dict[str, Any]]:
        normalized = provider if isinstance(provider, OAuthProvider) else OAuthProvider(str(provider).upper())
        return [
            row.as_dict()
            for row in self._registrations.values()
            if row.provider is normalized
        ]

    def inventory(self) -> list[dict[str, Any]]:
        with self._lock:
            return [registration.as_dict() for registration in self._registrations.values()]

    def handle(self, oauth_id: str) -> dict[str, Any]:
        return issue_oauth_handle(self.get(oauth_id)).as_dict()

    def risk_summary(self) -> dict[str, Any]:
        rows = sorted(self.inventory(), key=lambda row: int(row["risk_score"]), reverse=True)
        return {
            "registration_count": len(rows),
            "high_risk_count": sum(int(row["risk_score"]) >= 70 for row in rows),
            "maximum_risk_score": max((int(row["risk_score"]) for row in rows), default=0),
            "rows": rows,
            "execution_allowed": False,
        }

    def expiry_forecast(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        output = []
        for registration in self._registrations.values():
            expiry = _parse_time(registration.expiry)
            days = (expiry - now).total_seconds() / 86400 if expiry else None
            output.append(
                {
                    "oauth_id": registration.oauth_id,
                    "provider": registration.provider.value,
                    "expiry": registration.expiry,
                    "days_remaining": round(days, 2) if days is not None else None,
                    "expired": bool(days is not None and days <= 0),
                }
            )
        return output

    def rotation_readiness(self) -> dict[str, Any]:
        rows = [
            {
                "oauth_id": row.oauth_id,
                "provider": row.provider.value,
                "rotation_required": row.status in {
                    OAuthStatus.TOKEN_EXPIRED,
                    OAuthStatus.TOKEN_REVOKED,
                    OAuthStatus.ROTATION_REQUIRED,
                },
                "refresh_allowed": False,
                "automatic_rotation": False,
            }
            for row in self._registrations.values()
        ]
        return {"rows": rows, "refresh_performed": False, "execution_allowed": False}

    def _secret_reference(self, secret_uuid: str | None) -> str | None:
        if not secret_uuid:
            return None
        self.secrets.metadata(secret_uuid)
        return f"secret-handle:{secret_uuid}"

    @staticmethod
    def _risk_score(registration: OAuthRegistration) -> int:
        score = 20
        if registration.status is OAuthStatus.CONFIGURATION_REQUIRED:
            score += 25
        if registration.pkce_required and not registration.pkce_configured:
            score += 25
        if registration.refresh_capability:
            score += 10
        if registration.status in {
            OAuthStatus.TOKEN_EXPIRED,
            OAuthStatus.TOKEN_REVOKED,
            OAuthStatus.FAILED,
        }:
            score += 30
        return min(100, score)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


EnterpriseOAuthManager = OAuthManager


__all__ = ["DuplicateOAuthRegistration", "EnterpriseOAuthManager", "OAuthManager"]
