"""
Broker Registry
Capital Strata Systems (CSS)

Purpose:
- Maintain the authoritative registry of supported brokers.
- Provide metadata required by the Broker Bootstrap / Adapter Manager.
- Keep broker selection governance-controlled and explicit.

Rules:
- No silent fallback to another broker.
- Unsupported brokers must fail closed.
- Registry metadata must not include secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class BrokerSpec:
    """
    Immutable broker specification used by bootstrap and adapter layers.
    """

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
        supported_asset_classes=["spot_crypto"],
    ),
    "oanda": BrokerSpec(
        name="oanda",
        display_name="OANDA",
        pip_package="oandapyV20",
        credential_file=".env.oanda",
        supports_paper=True,
        supports_live=True,
        supported_asset_classes=["fx"],
    ),
    "alpaca": BrokerSpec(
        name="alpaca",
        display_name="Alpaca",
        pip_package="alpaca-py",
        credential_file=".env.alpaca",
        supports_paper=True,
        supports_live=True,
        supported_asset_classes=["equities", "crypto"],
    ),
}


def list_supported_brokers() -> List[str]:
    """
    Return sorted list of supported broker keys.
    """
    return sorted(BROKER_REGISTRY.keys())


def get_broker_spec(broker_name: str) -> BrokerSpec:
    """
    Fetch a broker specification by normalized broker name.

    Raises:
        KeyError: If the broker is not registered.
    """
    key = broker_name.strip().lower()
    if key not in BROKER_REGISTRY:
        supported = ", ".join(list_supported_brokers())
        raise KeyError(
            f"Unsupported broker '{broker_name}'. Supported brokers: {supported}"
        )
    return BROKER_REGISTRY[key]


def broker_supports_mode(broker_name: str, mode: str) -> bool:
    """
    Return True if the broker supports the requested mode.
    """
    spec = get_broker_spec(broker_name)
    mode_key = mode.strip().lower()

    if mode_key == "paper":
        return spec.supports_paper
    if mode_key == "live":
        return spec.supports_live

    raise ValueError("Mode must be either 'paper' or 'live'.")


def broker_supports_asset_class(broker_name: str, asset_class: str) -> bool:
    """
    Return True if the broker supports the requested asset class.
    """
    spec = get_broker_spec(broker_name)
    requested = asset_class.strip().lower()
    return requested in [a.lower() for a in spec.supported_asset_classes]
