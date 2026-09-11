from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .questrade_client import ProviderError, ProviderUnavailableError, QuestradeReadOnlyClient
from .questrade_oauth_manager import AuthRequiredError, ConfigurationRequiredError, TokenRefreshFailedError
from .questrade_provider_config import QuestradeProviderConfig, mask_account_identifier, select_account


def provider_failure_status(error: BaseException) -> str:
    if isinstance(error, (AuthRequiredError, TokenRefreshFailedError)):
        return "AUTH_REQUIRED"
    if isinstance(error, ConfigurationRequiredError):
        return "CONFIGURATION_REQUIRED"
    if isinstance(error, ProviderUnavailableError):
        return "PROVIDER_UNAVAILABLE"
    if isinstance(error, ProviderError):
        return "PROVIDER_RESPONSE_ERROR"
    if isinstance(error, RuntimeError) and str(error) == "CONFIGURATION_REQUIRED":
        return "CONFIGURATION_REQUIRED"
    return "PROVIDER_RESPONSE_ERROR"


def validate_readonly_provider(
    client: QuestradeReadOnlyClient,
    config: QuestradeProviderConfig,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect only harmless Questrade GET data and return redacted diagnostics."""
    config.require_enabled()
    accounts_payload = client.get_accounts()
    accounts = accounts_payload.get("accounts") if isinstance(accounts_payload, dict) else None
    selected = select_account(accounts if isinstance(accounts, list) else [], config.account_id)
    account_id = selected.get("number", selected.get("accountId"))
    if account_id is None:
        raise RuntimeError("PROVIDER_RESPONSE_ERROR")
    account_key = str(account_id)
    balances = client.get_balances(account_key)
    positions_payload = client.get_positions(account_key)
    positions = positions_payload.get("positions") if isinstance(positions_payload, dict) else None
    if not isinstance(positions, list):
        raise RuntimeError("PROVIDER_RESPONSE_ERROR")
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "provider_health": "AVAILABLE",
        "provider": "QUESTRADE",
        "mode": "LIVE_READ_ONLY",
        "masked_account_id": mask_account_identifier(account_key),
        "currency": selected.get("currency") or (balances.get("currency") if isinstance(balances, dict) else None),
        "balance_record_count": len(balances) if isinstance(balances, dict) else 0,
        "position_count": len(positions),
        "timestamp": observed.isoformat(),
        "freshness": "CURRENT",
        "rate_limit": {
            "remaining": client.last_rate_limit.remaining,
            "reset": client.last_rate_limit.reset,
        },
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = ["provider_failure_status", "validate_readonly_provider"]