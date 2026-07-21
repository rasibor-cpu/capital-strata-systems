"""
Capital Strata Systems (CSS) broker registry.

The registry is intentionally metadata-only: it lists approved brokers,
their dependency package, expected credential file, and supported modes/assets.
It does not contain secrets and it does not silently fall back to another
broker when a broker key is invalid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Type


@dataclass(frozen=True)
class BrokerSpec:
    name: str
    display_name: str
    pip_package: str
    credential_file: str
    supports_paper: bool
    supports_live: bool
    supported_asset_classes: List[str]


# Phase 177C Revision B — canonical Tier-1 metadata (IBKR/Alpaca removed from active set).
# Capability-rich registry lives in backend.app.brokers.canonical_tier1.
BROKER_REGISTRY: Dict[str, BrokerSpec] = {
    "coinbase": BrokerSpec(
        name="coinbase",
        display_name="Coinbase",
        pip_package="coinbase-advanced-py",
        credential_file="cdp_api_key.json",
        supports_paper=True,
        supports_live=True,  # live = LIVE_READ_ONLY / future; execution not enabled by registry
        supported_asset_classes=["crypto", "spot_crypto"],
    ),
    "binance": BrokerSpec(
        name="binance",
        display_name="Binance",
        pip_package="python-binance",
        credential_file=".env.binance",
        supports_paper=True,
        supports_live=True,
        supported_asset_classes=["crypto", "spot_crypto"],
    ),
    "oanda": BrokerSpec(
        name="oanda",
        display_name="OANDA",
        pip_package="oandapyV20",
        credential_file=".env.oanda",
        supports_paper=True,
        supports_live=True,
        supported_asset_classes=["fx", "forex"],
    ),
    "questrade": BrokerSpec(
        name="questrade",
        display_name="Questrade",
        pip_package="",
        credential_file=".env.questrade",
        supports_paper=True,
        supports_live=True,
        supported_asset_classes=["equities_ca", "etf", "option"],
    ),
}


def _normalize_broker_name(broker_name: str) -> str:
    return str(broker_name or "").strip().lower()


def list_supported_brokers() -> List[str]:
    return sorted(BROKER_REGISTRY.keys())


def get_broker_spec(broker_name: str) -> BrokerSpec:
    key = _normalize_broker_name(broker_name)
    if key not in BROKER_REGISTRY:
        supported = ", ".join(list_supported_brokers())
        raise KeyError(f"Unsupported broker '{broker_name}'. Supported brokers: {supported}")
    return BROKER_REGISTRY[key]


def broker_supports_mode(broker_name: str, mode: str) -> bool:
    spec = get_broker_spec(broker_name)
    mode_key = str(mode or "").strip().lower()
    if mode_key == "paper":
        return spec.supports_paper
    if mode_key == "live":
        return spec.supports_live
    raise ValueError("Mode must be either 'paper' or 'live'.")


def broker_supports_asset_class(broker_name: str, asset_class: str) -> bool:
    spec = get_broker_spec(broker_name)
    requested = str(asset_class or "").strip().lower()
    return requested in {asset.lower() for asset in spec.supported_asset_classes}


def get_adapter(broker_name: str) -> Type[object]:
    key = _normalize_broker_name(broker_name)
    get_broker_spec(key)

    if key == "coinbase":
        from backend.broker.coinbase_adapter import CoinbaseAdapter

        return CoinbaseAdapter

    if key == "oanda":
        from backend.app.brokers.oanda_adapter import OandaAdapter

        return OandaAdapter

    # Phase 178B: expected incomplete-adapter conditions are structured states.
    # These classes are source-only/read-only and never authenticate or execute.
    if key == "binance":
        from backend.app.brokers.operational_adapter import BinanceOperationalAdapter

        return BinanceOperationalAdapter

    if key == "questrade":
        from backend.app.brokers.operational_adapter import QuestradeOperationalAdapter

        return QuestradeOperationalAdapter

    # get_broker_spec above guarantees this is unreachable unless the registry
    # and adapter mapping drift, which is an unexpected software fault.
    raise RuntimeError(f"Tier-1 broker adapter mapping is corrupted for '{broker_name}'")


def get_operational_adapter(
    broker_name: str,
    *,
    configuration: Dict[str, object] | None = None,
    evidence: Dict[str, object] | None = None,
) -> object:
    """Return the canonical structured-state adapter for any Tier-1 broker."""
    get_broker_spec(broker_name)
    from backend.app.brokers.operational_adapter import get_operational_adapter as build

    return build(broker_name, configuration=configuration, evidence=evidence)
