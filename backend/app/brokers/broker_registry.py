"""
Broker Registry
Capital Strata Systems (CSS)

Purpose:
- Maintain the authoritative registry of supported brokers.
- Provide metadata required by the Broker Bootstrap / Adapter Manager.
- Keep broker selection governance-controlled and explicit.
- Resolve adapter classes lazily so missing optional broker packages do not
  break unrelated brokers.

Rules:
- No silent fallback to another broker.
- Unsupported brokers must fail closed.
- Registry metadata must not include secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type


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
        supported_asset_classes=["spot_crypto", "crypto"],
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
        supported_asset_classes=["equities", "stocks", "crypto"],
    ),
    "futures_sim": BrokerSpec(
        name="futures_sim",
        display_name="Futures Simulator",
        pip_package="",
        credential_file="",
        supports_paper=True,
        supports_live=False,
        supported_asset_classes=["futures"],
    ),
}


BROKER_ALIASES: Dict[str, str] = {
    "coinbase_advanced": "coinbase",
    "cb": "coinbase",
    "oanda_fx": "oanda",
    "fx": "oanda",
    "alpaca_paper": "alpaca",
    "futures": "futures_sim",
    "futures_simulator": "futures_sim",
}


def normalize_broker_name(broker_name: str) -> str:
    """
    Normalize broker names and aliases to registry keys.
    """
    key = (broker_name or "").strip().lower()
    return BROKER_ALIASES.get(key, key)


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
    key = normalize_broker_name(broker_name)
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
    mode_key = (mode or "").strip().lower()

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
    requested = (asset_class or "").strip().lower()
    return requested in [a.lower() for a in spec.supported_asset_classes]


def get_adapter(broker_name: str) -> Optional[Type[Any]]:
    """
    Resolve and return the adapter class for the selected broker.

    This is intentionally lazy so one broken optional dependency does not
    prevent the rest of CSS from loading.

    Returns:
        Adapter class or None if unresolved.
    """
    key = normalize_broker_name(broker_name)

    if key == "oanda":
        try:
            from .oanda_adapter import OandaAdapter
            return OandaAdapter
        except Exception:
            return None

    if key == "alpaca":
        try:
            from .alpaca_adapter import AlpacaAdapter
            return AlpacaAdapter
        except Exception:
            return None

    if key == "futures_sim":
        try:
            from .futures_sim_adapter import FuturesSimAdapter
            return FuturesSimAdapter
        except Exception:
            return None

    if key == "coinbase":
        try:
            from backend.broker.coinbase_adapter import CoinbaseAdapter
            return CoinbaseAdapter
        except Exception:
            try:
                from .coinbase_adapter import CoinbaseAdapter
                return CoinbaseAdapter
            except Exception:
                return None

    return None