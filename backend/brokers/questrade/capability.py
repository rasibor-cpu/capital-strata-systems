"""Questrade capability and endpoint configuration (advisory)."""

from __future__ import annotations

from typing import Any

QUESTRADE_ENDPOINTS = {
    "login": "https://login.questrade.com/oauth2/token",
    "api_base_placeholder": "https://api01.iq.questrade.com/v1",  # server URL returned by auth
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
        "order_submission_supported_in_phase_178a": False,
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
        "credential_file": ".env.questrade",
        "secrets_hardcoded": False,
        "provenance": "CONFIGURATION|BROKER",
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = ["QUESTRADE_ENDPOINTS", "RATE_LIMIT_HINTS", "questrade_capability_descriptor"]
