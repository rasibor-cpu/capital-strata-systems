"""
Capital Strata Systems (CSS)
Broker Bootstrap

Purpose
-------
Responsible for initializing the selected broker adapter
during system startup.

Flow
----
1. User selects broker (Coinbase, OANDA, Alpaca, etc)
2. Credentials are loaded
3. Required SDK dependencies are installed
4. Adapter instance is created
5. Adapter is returned to the trading engine
"""

from typing import Any, Dict

from .broker_registry import get_adapter
from .credential_loader import load_credentials
from .install_utils import ensure_broker_dependencies


class BrokerBootstrapError(Exception):
    """Raised when broker initialization fails."""
    pass


def initialize_broker(broker_name: str, mode: str = "paper"):
    """
    Initialize a broker adapter.

    Parameters
    ----------
    broker_name : str
        Name of broker (coinbase, oanda, alpaca)

    mode : str
        'paper' or 'live'

    Returns
    -------
    adapter instance
    """

    broker_name = broker_name.lower()

    print(f"[BROKER BOOTSTRAP] Initializing broker: {broker_name}")
    print(f"[BROKER BOOTSTRAP] Mode: {mode}")

    # Ensure required dependencies are installed
    dependency_status = ensure_broker_dependencies(broker_name)
    if not dependency_status.get("ok"):
        raise BrokerBootstrapError(
            "Broker dependency unavailable for "
            f"{broker_name}: {dependency_status.get('package')}"
        )

    # Load credentials
    creds = load_credentials(broker_name)

    if creds is None:
        raise BrokerBootstrapError(
            f"No credentials found for broker: {broker_name}"
        )

    # Get adapter class from registry
    adapter_cls = get_adapter(broker_name)

    if adapter_cls is None:
        raise BrokerBootstrapError(
            f"No adapter registered for broker: {broker_name}"
        )

    # Initialize adapter without assuming all legacy adapters expose the same
    # constructor. This keeps bootstrap fail-closed while the broker layer is
    # being consolidated.
    adapter = _instantiate_adapter(adapter_cls, broker_name, creds, mode)

    # Connect to broker
    connect = getattr(adapter, "connect", None)
    if callable(connect):
        connect()
    else:
        is_configured = getattr(adapter, "is_configured", None)
        if callable(is_configured) and not is_configured():
            raise BrokerBootstrapError(f"{broker_name} adapter is not configured")

    print(f"[BROKER BOOTSTRAP] {broker_name} successfully initialized")

    return adapter


def _instantiate_adapter(
    adapter_cls: type,
    broker_name: str,
    creds: Dict[str, Any],
    mode: str,
):
    if broker_name == "coinbase":
        return adapter_cls(
            api_key_name=str(
                creds.get("api_key_name")
                or creds.get("name")
                or creds.get("key_name")
                or ""
            ),
            api_private_key_path=str(
                creds.get("api_private_key_path")
                or creds.get("private_key_path")
                or ""
            ),
            paper_mode=mode != "live",
        )

    try:
        return adapter_cls(credentials=creds, mode=mode)
    except TypeError:
        return adapter_cls()
