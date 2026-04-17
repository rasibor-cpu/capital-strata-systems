"""
Capital Strata Systems (CSS)
Broker Bootstrap

Purpose
-------
Responsible for initializing the selected broker adapter during system startup.

Flow
----
1. User selects broker (Coinbase, OANDA, Alpaca, Futures Sim, etc.)
2. Broker registry validates selection
3. Required SDK dependencies are checked
4. Credentials are loaded when available/required
5. Adapter instance is created using a compatibility-safe constructor path
6. Adapter is returned to the trading engine

Safety
------
- No silent fallback to another broker.
- Missing live credentials fail closed.
- Paper mode can proceed where broker supports paper mode.
- Existing adapters that use no-arg constructors remain supported.
"""

from __future__ import annotations

from typing import Any, Optional

from .broker_registry import (
    broker_supports_mode,
    get_adapter,
    get_broker_spec,
    normalize_broker_name,
)
from .credential_loader import load_credentials
from .install_utils import ensure_broker_dependencies


class BrokerBootstrapError(Exception):
    """Raised when broker initialization fails."""


def _instantiate_adapter(
    adapter_cls: Any,
    broker_name: str,
    mode: str,
    credentials: Optional[dict],
) -> Any:
    """
    Instantiate broker adapters safely across different constructor styles.

    Supported patterns:
    1. Adapter(credentials=..., mode=...)
    2. Adapter(mode=...)
    3. Adapter()
    4. Coinbase legacy adapter with paper_mode flag
    """

    key = normalize_broker_name(broker_name)
    mode_key = (mode or "paper").strip().lower()

    if key == "coinbase":
        # The existing backend.broker.coinbase_adapter.CoinbaseAdapter usually
        # supports paper_mode rather than mode/credentials constructor args.
        try:
            return adapter_cls(paper_mode=(mode_key != "live"))
        except TypeError:
            pass

    try:
        return adapter_cls(credentials=credentials, mode=mode_key)
    except TypeError:
        pass

    try:
        return adapter_cls(mode=mode_key)
    except TypeError:
        pass

    try:
        return adapter_cls()
    except TypeError as exc:
        raise BrokerBootstrapError(
            f"Unable to initialize adapter for broker '{broker_name}'. "
            f"Unsupported constructor signature: {exc}"
        ) from exc


def initialize_broker(broker_name: str, mode: str = "paper") -> Any:
    """
    Initialize a broker adapter.

    Parameters
    ----------
    broker_name:
        Name of broker: coinbase, oanda, alpaca, futures_sim.

    mode:
        'paper' or 'live'.

    Returns
    -------
    adapter instance
    """

    broker_key = normalize_broker_name(broker_name)
    mode_key = (mode or "paper").strip().lower()

    print(f"[BROKER BOOTSTRAP] Initializing broker: {broker_key}")
    print(f"[BROKER BOOTSTRAP] Mode: {mode_key}")

    try:
        spec = get_broker_spec(broker_key)
    except Exception as exc:
        raise BrokerBootstrapError(str(exc)) from exc

    if not broker_supports_mode(broker_key, mode_key):
        raise BrokerBootstrapError(
            f"Broker '{broker_key}' does not support mode '{mode_key}'."
        )

    dep_status = ensure_broker_dependencies(broker_key, auto_install=False)
    if not dep_status.get("ok"):
        raise BrokerBootstrapError(
            f"Dependency missing for broker '{broker_key}': "
            f"{dep_status.get('package')}. Install required."
        )

    try:
        creds = load_credentials(broker_key, mode=mode_key)
    except Exception as exc:
        raise BrokerBootstrapError(
            f"Credential load failed for broker '{broker_key}': {exc}"
        ) from exc

    if mode_key == "live" and not creds and spec.credential_file:
        raise BrokerBootstrapError(
            f"No live credentials found for broker: {broker_key}"
        )

    adapter_cls = get_adapter(broker_key)
    if adapter_cls is None:
        raise BrokerBootstrapError(
            f"No adapter registered for broker: {broker_key}"
        )

    adapter = _instantiate_adapter(
        adapter_cls=adapter_cls,
        broker_name=broker_key,
        mode=mode_key,
        credentials=creds,
    )

    # Connect only if the adapter actually exposes connect().
    if hasattr(adapter, "connect") and callable(getattr(adapter, "connect")):
        try:
            adapter.connect()
        except Exception as exc:
            raise BrokerBootstrapError(
                f"Broker '{broker_key}' connect() failed: {exc}"
            ) from exc

    # Validate basic configuration if the adapter supports is_configured().
    if hasattr(adapter, "is_configured") and callable(getattr(adapter, "is_configured")):
        try:
            configured = bool(adapter.is_configured())
        except Exception:
            configured = False

        if mode_key == "live" and not configured:
            raise BrokerBootstrapError(
                f"Broker '{broker_key}' is not configured for live mode."
            )

    print(f"[BROKER BOOTSTRAP] {broker_key} successfully initialized")

    return adapter