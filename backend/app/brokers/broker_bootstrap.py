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

from typing import Optional

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
    ensure_broker_dependencies(broker_name)

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

    # Initialize adapter
    adapter = adapter_cls(credentials=creds, mode=mode)

    # Connect to broker
    adapter.connect()

    print(f"[BROKER BOOTSTRAP] {broker_name} successfully initialized")

    return adapter
