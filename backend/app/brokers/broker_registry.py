from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Type


@dataclass(frozen=True)
class BrokerSpec:
    name: str
    display_name: str
    adapter_class: Optional[Type[Any]] = None
    supported_asset_classes: Tuple[str, ...] = ("crypto", "fx", "futures", "options")
    supported_modes: Tuple[str, ...] = ("paper", "live")
    pip_package: str = ""
    credential_file: str = ".env"


try:
    from backend.broker.coinbase_adapter import CoinbaseAdapter
except Exception:
    CoinbaseAdapter = None

try:
    from backend.app.brokers.oanda_adapter import OandaAdapter
except Exception:
    OandaAdapter = None

try:
    from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
except Exception:
    FuturesSimAdapter = None


BROKER_REGISTRY: Dict[str, BrokerSpec] = {
    "coinbase": BrokerSpec(
        name="coinbase",
        display_name="Coinbase",
        adapter_class=CoinbaseAdapter,
        supported_asset_classes=("crypto",),
        supported_modes=("paper", "live"),
        pip_package="coinbase-advanced-py",
        credential_file=".env",
    ),
    "oanda": BrokerSpec(
        name="oanda",
        display_name="OANDA",
        adapter_class=OandaAdapter,
        supported_asset_classes=("fx",),
        supported_modes=("paper", "live"),
        pip_package="oandapyV20",
        credential_file=".env",
    ),
    "futures_sim": BrokerSpec(
        name="futures_sim",
        display_name="Futures Simulation",
        adapter_class=FuturesSimAdapter,
        supported_asset_classes=("futures",),
        supported_modes=("paper", "live"),
        pip_package="",
        credential_file=".env",
    ),
}

BROKER_ALIASES: Dict[str, str] = {
    "coinbase_advanced": "coinbase",
    "coinbaseadvanced": "coinbase",
    "cb": "coinbase",
    "fx": "oanda",
    "oanda_fx": "oanda",
    "futures": "futures_sim",
    "futures-sim": "futures_sim",
    "future_sim": "futures_sim",
}


def normalize_broker_name(broker_name: str) -> str:
    key = str(broker_name or "").strip().lower()
    return BROKER_ALIASES.get(key, key)


def list_supported_brokers():
    return sorted(BROKER_REGISTRY.keys())


def get_broker_spec(broker_name: str) -> BrokerSpec:
    key = normalize_broker_name(broker_name)

    if key not in BROKER_REGISTRY:
        raise ValueError(
            f"Unsupported broker '{broker_name}'. "
            f"Supported brokers: {', '.join(list_supported_brokers())}"
        )

    return BROKER_REGISTRY[key]


def get_adapter(broker_name: str):
    spec = get_broker_spec(broker_name)
    return spec.adapter_class


def broker_supports_mode(broker_name: str, mode: str) -> bool:
    spec = get_broker_spec(broker_name)
    mode_key = str(mode or "").strip().lower()
    return mode_key in spec.supported_modes


def broker_supports_asset_class(broker_name: str, asset_class: str) -> bool:
    spec = get_broker_spec(broker_name)
    asset_key = str(asset_class or "").strip().lower()
    return asset_key in spec.supported_asset_classes