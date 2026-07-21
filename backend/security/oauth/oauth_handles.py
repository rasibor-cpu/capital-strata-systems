"""Opaque OAuth registration handles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any

from backend.security.oauth.oauth_models import OAuthRegistration


@dataclass(frozen=True)
class OAuthHandle:
    handle: str
    oauth_id: str
    provider: str
    secret_handles: tuple[str, ...]
    scopes: tuple[str, ...]
    environment: str
    token_type: str
    status: str
    issued: str
    expiry: str | None
    refresh_capability: bool
    owner: str
    risk_score: int
    correlation_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "plaintext_tokens_returned": False,
            "authorization_enabled": False,
            "refresh_enabled": False,
            "execution_allowed": False,
        }


def issue_oauth_handle(registration: OAuthRegistration) -> OAuthHandle:
    digest = hashlib.sha256(
        (
            f"{registration.oauth_id}|{registration.provider.value}|"
            f"{registration.correlation_id}"
        ).encode()
    ).hexdigest()
    secret_handles = tuple(
        value
        for value in (
            registration.client_id_handle,
            registration.client_secret_handle,
            registration.refresh_token_handle,
            registration.access_token_handle,
        )
        if value
    )
    return OAuthHandle(
        handle=f"OH-{digest[:32].upper()}",
        oauth_id=registration.oauth_id,
        provider=registration.provider.value,
        secret_handles=secret_handles,
        scopes=registration.scopes,
        environment=registration.environment,
        token_type=registration.token_type.value,
        status=registration.status.value,
        issued=registration.issued,
        expiry=registration.expiry,
        refresh_capability=registration.refresh_capability,
        owner=registration.owner,
        risk_score=registration.risk_score,
        correlation_id=registration.correlation_id,
    )


__all__ = ["OAuthHandle", "issue_oauth_handle"]
