"""Secure, presence-only Questrade configuration contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import re
from typing import Any, Mapping


_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}$")
_ENVIRONMENTS = {"PRODUCTION", "PRACTICE"}


@dataclass(frozen=True)
class QuestradeSecureConfiguration:
    """References secrets; never contains OAuth token values."""

    refresh_token_ref: str | None = None
    access_token_ref: str | None = None
    token_store_id: str | None = None
    selected_account_hash: str | None = None
    preferred_account_type: str | None = None
    api_environment: str = "PRODUCTION"
    callback_metadata_ref: str | None = None
    secret_store_provider: str = "UNCONFIGURED"
    scope: str = "READ_ONLY"
    authorization_enabled: bool = False

    @classmethod
    def from_environment_presence(cls, env: Mapping[str, str] | None = None) -> "QuestradeSecureConfiguration":
        source = os.environ if env is None else env
        refresh_present = bool(source.get("QUESTRADE_REFRESH_TOKEN"))
        access_present = bool(source.get("QUESTRADE_ACCESS_TOKEN"))
        return cls(
            refresh_token_ref="env:QUESTRADE_REFRESH_TOKEN" if refresh_present else None,
            access_token_ref="env:QUESTRADE_ACCESS_TOKEN" if access_present else None,
            token_store_id=source.get("QUESTRADE_TOKEN_STORE_ID") or None,
            selected_account_hash=source.get("QUESTRADE_ACCOUNT_HASH") or None,
            preferred_account_type=source.get("QUESTRADE_ACCOUNT_TYPE") or None,
            api_environment=str(source.get("QUESTRADE_API_ENVIRONMENT") or "PRODUCTION").upper(),
            callback_metadata_ref=source.get("QUESTRADE_CALLBACK_METADATA_REF") or None,
            secret_store_provider=source.get("QUESTRADE_SECRET_STORE_PROVIDER") or "ENVIRONMENT_REFERENCE",
            authorization_enabled=False,
        )

    def validate(self) -> dict[str, Any]:
        invalid_references = [
            name
            for name, value in (
                ("refresh_token_ref", self.refresh_token_ref),
                ("access_token_ref", self.access_token_ref),
                ("token_store_id", self.token_store_id),
                ("callback_metadata_ref", self.callback_metadata_ref),
            )
            if value and not _REFERENCE.fullmatch(value)
        ]
        environment_valid = self.api_environment.upper() in _ENVIRONMENTS
        read_only = self.scope.upper() == "READ_ONLY"
        token_reference_present = bool(self.refresh_token_ref or self.token_store_id)
        valid = not invalid_references and environment_valid and read_only
        return {
            "valid": valid,
            "token_reference_present": token_reference_present,
            "access_token_reference_present": bool(self.access_token_ref),
            "selected_account_reference_present": bool(self.selected_account_hash),
            "invalid_reference_fields": invalid_references,
            "environment_valid": environment_valid,
            "read_only_scope": read_only,
            "authorization_enabled": False,
            "execution_allowed": False,
        }

    def sanitized_summary(self) -> dict[str, Any]:
        check = self.validate()
        return {
            "configuration_present": bool(check["token_reference_present"]),
            "access_token_reference_present": check["access_token_reference_present"],
            "token_store_configured": bool(self.token_store_id),
            "selected_account_configured": check["selected_account_reference_present"],
            "preferred_account_type": self.preferred_account_type,
            "api_environment": self.api_environment.upper(),
            "callback_metadata_configured": bool(self.callback_metadata_ref),
            "secret_store_provider": self.secret_store_provider,
            "scope": "READ_ONLY",
            "authorization_enabled": False,
            "valid": check["valid"],
            "invalid_reference_fields": check["invalid_reference_fields"],
            "secrets_returned": False,
            "execution_allowed": False,
        }

    def as_reference_dict(self) -> dict[str, Any]:
        """Internal reference-only representation; never return it from APIs."""
        return asdict(self)


__all__ = ["QuestradeSecureConfiguration"]
