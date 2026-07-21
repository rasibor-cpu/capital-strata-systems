"""Questrade capability and endpoint configuration (advisory)."""

from __future__ import annotations

from typing import Any

QUESTRADE_ENDPOINTS = {
    "login": "https://login.questrade.com/oauth2/token",
    "api_server_source": "OAUTH_TOKEN_RESPONSE",
    "accounts": "/accounts",
    "positions": "/accounts/{id}/positions",
    "balances": "/accounts/{id}/balances",
    "markets": "/markets",
    "symbols": "/symbols",
    "quotes": "/markets/quotes",
    "option_chain": "/symbols/{id}/options",
}

RATE_LIMIT_HINTS = {
    "requests_per_second_soft": 2,
    "burst_soft": 10,
    "note": "Exact Questrade limits require live auth discovery; soft hints only",
}


def questrade_capability_descriptor() -> dict[str, Any]:
    return {
        "broker": "QUESTRADE",
        "listed_equity_options": True,
        "equities_ca": True,
        "equities_us": True,
        "etf": True,
        "fx": False,
        "crypto": False,
        "read_only_advisory_supported": True,
        "read_operations": [
            "oauth_token_metadata",
            "accounts",
            "balances",
            "positions",
            "activities",
            "symbols",
            "quotes",
            "option_chain_metadata",
            "market_status",
        ],
        "write_operations": [],
        "order_submission_supported": False,
        "order_modification_supported": False,
        "order_cancellation_supported": False,
        "exercise_supported": False,
        "authentication_activated": False,
        "adapter_state": "CONFIGURATION_REQUIRED",
        "endpoints": dict(QUESTRADE_ENDPOINTS),
        "rate_limit_hints": dict(RATE_LIMIT_HINTS),
        "credential_env_keys": [
            "QUESTRADE_REFRESH_TOKEN",
            "QUESTRADE_ACCESS_TOKEN",
            "QUESTRADE_API_SERVER",
            "QUESTRADE_ACCOUNT_ID",
        ],
        "secure_configuration_refs": [
            "QUESTRADE_TOKEN_STORE_ID",
            "QUESTRADE_SECRET_STORE_PROVIDER",
            "QUESTRADE_ACCOUNT_HASH",
        ],
        "plaintext_credential_file_supported": False,
        "api_server_discovered_from_token_response": True,
        "api_server_domain_allowlist": "api[0-9]+.iq.questrade.com",
        "secrets_hardcoded": False,
        "provenance": "CONFIGURATION|BROKER",
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = ["QUESTRADE_ENDPOINTS", "RATE_LIMIT_HINTS", "questrade_capability_descriptor"]
