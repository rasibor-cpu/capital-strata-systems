"""Canonical metadata-only OAuth contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OAuthProvider(str, Enum):
    QUESTRADE = "QUESTRADE"
    COINBASE = "COINBASE"
    BINANCE = "BINANCE"
    OANDA = "OANDA"
    MICROSOFT = "MICROSOFT"
    GOOGLE = "GOOGLE"
    CUSTOM = "CUSTOM"


class OAuthStatus(str, Enum):
    UNCONFIGURED = "UNCONFIGURED"
    REGISTERED = "REGISTERED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    AUTHORIZATION_PENDING = "AUTHORIZATION_PENDING"
    AUTHORIZED = "AUTHORIZED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    ROTATION_REQUIRED = "ROTATION_REQUIRED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


class OAuthTokenType(str, Enum):
    AUTHORIZATION_CODE = "AUTHORIZATION_CODE"
    ACCESS_TOKEN = "ACCESS_TOKEN"
    REFRESH_TOKEN = "REFRESH_TOKEN"
    CLIENT_CREDENTIALS = "CLIENT_CREDENTIALS"
    NONE = "NONE"


@dataclass(frozen=True)
class OAuthRegistration:
    oauth_id: str
    provider: OAuthProvider
    environment: str
    owner: str
    scopes: tuple[str, ...]
    token_type: OAuthTokenType
    status: OAuthStatus
    issued: str
    expiry: str | None
    refresh_capability: bool
    correlation_id: str
    client_id_handle: str | None
    client_secret_handle: str | None
    refresh_token_handle: str | None
    access_token_handle: str | None
    redirect_uri: str | None
    pkce_required: bool
    pkce_configured: bool
    risk_score: int
    disabled: bool = False
    validation_history: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provider"] = self.provider.value
        payload["token_type"] = self.token_type.value
        payload["status"] = self.status.value
        payload["oauth_handle"] = "OH-" + hashlib.sha256(
            f"{self.oauth_id}|{self.provider.value}|{self.correlation_id}".encode()
        ).hexdigest()[:32].upper()
        payload["token_values_returned"] = False
        payload["authorization_performed"] = False
        payload["refresh_performed"] = False
        payload["execution_allowed"] = False
        return payload


@dataclass(frozen=True)
class OAuthRisk:
    oauth_id: str
    score: int
    factors: tuple[str, ...]
    status: str


__all__ = [
    "OAuthProvider",
    "OAuthRegistration",
    "OAuthRisk",
    "OAuthStatus",
    "OAuthTokenType",
    "utc_now",
]
