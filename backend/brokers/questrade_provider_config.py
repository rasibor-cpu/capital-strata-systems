from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping


@dataclass(frozen=True)
class QuestradeProviderConfig:
    enabled: bool = False
    credential_source: str = "state/questrade/credentials.json"
    account_id: str | None = None
    freshness_threshold: timedelta = timedelta(minutes=5)
    environment: str = "production"

    @classmethod
    def from_mapping(cls, values: Mapping[str, object] | None = None) -> "QuestradeProviderConfig":
        values = values or {}
        enabled = values.get("enabled", False) is True
        environment = str(values.get("environment", "production")).lower()
        if environment not in {"production", "practice"}:
            raise ValueError("Questrade environment must be production or practice")
        threshold = int(values.get("freshness_threshold_seconds", 300))
        if threshold <= 0:
            raise ValueError("freshness threshold must be positive")
        return cls(
            enabled=enabled,
            credential_source=str(values.get("credential_source", cls.credential_source)),
            account_id=str(values["account_id"]) if values.get("account_id") else None,
            freshness_threshold=timedelta(seconds=threshold),
            environment=environment,
        )

    def require_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError("CONFIGURATION_REQUIRED")


def select_account(accounts: list[Mapping[str, object]], configured_id: str | None = None) -> Mapping[str, object]:
    if not accounts:
        raise RuntimeError("PROVIDER_RESPONSE_ERROR")
    if configured_id:
        for account in accounts:
            if str(account.get("number")) == configured_id or str(account.get("accountId")) == configured_id:
                return account
        raise RuntimeError("PROVIDER_RESPONSE_ERROR")
    if len(accounts) != 1:
        raise RuntimeError("CONFIGURATION_REQUIRED")
    return accounts[0]


def mask_account_identifier(value: object) -> str:
    text = str(value or "")
    return "*" * max(0, len(text) - 4) + text[-4:] if text else "<unknown>"


__all__ = ["QuestradeProviderConfig", "mask_account_identifier", "select_account"]
