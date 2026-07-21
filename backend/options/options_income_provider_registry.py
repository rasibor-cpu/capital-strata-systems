"""Phase 178A — option-chain / market-data provider plugin registry.

No paid vendor is registered by default. Operators must explicitly configure
an approved provider; otherwise OPTION_CHAIN_PROVIDER_NOT_CONFIGURED.
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.options.options_income_freshness import utc_now


class MarketDataProviderPlugin(Protocol):
    name: str

    def readiness(self) -> dict[str, Any]: ...

    def get_underlying_quote(self, symbol: str) -> dict[str, Any]: ...


class OptionChainProviderPlugin(Protocol):
    name: str

    def readiness(self) -> dict[str, Any]: ...

    def get_option_chain(self, underlying: str) -> dict[str, Any]: ...


class HoldingsProviderPlugin(Protocol):
    name: str

    def readiness(self) -> dict[str, Any]: ...

    def get_holdings_snapshot(self) -> dict[str, Any]: ...


_MARKET_DATA: dict[str, MarketDataProviderPlugin] = {}
_OPTION_CHAIN: dict[str, OptionChainProviderPlugin] = {}
_HOLDINGS: dict[str, HoldingsProviderPlugin] = {}


def register_market_data_provider(plugin: MarketDataProviderPlugin) -> None:
    _MARKET_DATA[str(plugin.name)] = plugin


def register_option_chain_provider(plugin: OptionChainProviderPlugin) -> None:
    _OPTION_CHAIN[str(plugin.name)] = plugin


def register_holdings_provider(plugin: HoldingsProviderPlugin) -> None:
    _HOLDINGS[str(plugin.name)] = plugin


def clear_provider_plugins() -> None:
    """Test helper — clears in-process registries."""
    _MARKET_DATA.clear()
    _OPTION_CHAIN.clear()
    _HOLDINGS.clear()


def get_market_data_provider(name: str | None = None) -> MarketDataProviderPlugin | None:
    if name:
        return _MARKET_DATA.get(name)
    if len(_MARKET_DATA) == 1:
        return next(iter(_MARKET_DATA.values()))
    return None


def get_option_chain_provider(name: str | None = None) -> OptionChainProviderPlugin | None:
    if name:
        return _OPTION_CHAIN.get(name)
    if len(_OPTION_CHAIN) == 1:
        return next(iter(_OPTION_CHAIN.values()))
    return None


def get_holdings_provider(name: str | None = None) -> HoldingsProviderPlugin | None:
    if name:
        return _HOLDINGS.get(name)
    if len(_HOLDINGS) == 1:
        return next(iter(_HOLDINGS.values()))
    return None


def provider_registry_status() -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "market_data_providers": sorted(_MARKET_DATA.keys()),
        "option_chain_providers": sorted(_OPTION_CHAIN.keys()),
        "holdings_providers": sorted(_HOLDINGS.keys()),
        "option_chain_status": (
            "READY_FOR_CONFIGURED_PROVIDER"
            if _OPTION_CHAIN
            else "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"
        ),
        "market_data_status": "READY_FOR_CONFIGURED_PROVIDER" if _MARKET_DATA else "MARKET_DATA_PROVIDER_NOT_CONFIGURED",
        "holdings_status": "READY_FOR_CONFIGURED_PROVIDER" if _HOLDINGS else "ACCOUNT_HOLDINGS_PROVIDER_NOT_CONFIGURED",
        "paid_vendor_registered": False,
        "scraping_enabled": False,
        "advisory_only": True,
        "execution_allowed": False,
        "provenance": "CONFIGURATION",
    }


__all__ = [
    "HoldingsProviderPlugin",
    "MarketDataProviderPlugin",
    "OptionChainProviderPlugin",
    "clear_provider_plugins",
    "get_holdings_provider",
    "get_market_data_provider",
    "get_option_chain_provider",
    "provider_registry_status",
    "register_holdings_provider",
    "register_market_data_provider",
    "register_option_chain_provider",
]
