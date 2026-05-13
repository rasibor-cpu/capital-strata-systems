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


BROKER_REGISTRY: Dict[str, BrokerSpec] = {
    "coinbase": BrokerSpec(
        name="coinbase",
        display_name="Coinbase",
        pip_package="coinbase-advanced-py",
        credential_file="cdp_api_key.json",
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
    "alpaca": BrokerSpec(
        name="alpaca",
        display_name="Alpaca",
        pip_package="alpaca-py",
        credential_file=".env.alpaca",
        supports_paper=True,
        supports_live=True,
        supported_asset_classes=["equities", "stocks", "crypto"],
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

    raise KeyError(
        f"No adapter class is available for broker '{broker_name}'. "
        "The broker is registered but not executable in this runtime."
    )
