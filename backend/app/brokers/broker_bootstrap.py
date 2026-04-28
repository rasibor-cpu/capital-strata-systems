"""
Capital Strata Systems (CSS)
Broker Bootstrap — PCNRASS SAFE PAPER/LIVE VERSION

Purpose
-------
Responsible for initializing the selected broker adapter during system startup.

PCNRASS Policy
--------------
- Paper mode must be allowed for safe dashboard/paper testing.
- Live mode must remain strict and fail closed when credentials/configuration are missing.
- Coinbase paper mode must NOT require live credentials.
- Coinbase live mode must NOT silently fall back to paper.
- No silent fallback to another broker.
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
    1. Coinbase paper adapter with paper_mode=True
    2. Coinbase live adapter with paper_mode=False
    3. Adapter(credentials=..., mode=...)
    4. Adapter(mode=...)
    5. Adapter()

    Critical Coinbase rule:
    - Paper mode is allowed for safe dashboard/paper testing.
    - Live mode must remain explicitly live and must not silently fall back to paper.
    """

    key = normalize_broker_name(broker_name)
    mode_key = (mode or "paper").strip().lower()

    if key == "coinbase":
        if mode_key == "paper":
            try:
                return adapter_cls(paper_mode=True)
            except TypeError:
                pass

        if mode_key == "live":
            try:
                return adapter_cls(paper_mode=False)
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

    # PCNRASS: Paper mode should not require live credential loading.
    # Live mode remains strict and fails closed.
    creds: Optional[dict] = None
    if mode_key == "live":
        try:
            creds = load_credentials(broker_key, mode=mode_key)
        except Exception as exc:
            raise BrokerBootstrapError(
                f"Credential load failed for broker '{broker_key}': {exc}"
            ) from exc

        if not creds and spec.credential_file:
            raise BrokerBootstrapError(
                f"No live credentials found for broker: {broker_key}"
            )
    else:
        try:
            creds = load_credentials(broker_key, mode=mode_key)
        except Exception:
            creds = None

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

    # Coinbase final safety verification:
    # - Paper mode may have paper_mode=True.
    # - Live mode must not initialize as paper.
    if broker_key == "coinbase":
        paper_mode_value = getattr(adapter, "paper_mode", None)

        if mode_key == "live" and paper_mode_value is True:
            raise BrokerBootstrapError(
                "SYSTEM BLOCKED: Coinbase adapter initialized in paper_mode=True "
                "during live startup. Live mode refuses to continue."
            )

        if mode_key == "paper":
            try:
                setattr(adapter, "paper_mode", True)
            except Exception:
                pass

    # Connect only if the adapter exposes connect().
    # In paper mode, connect failure should not kill dashboard startup.
    if hasattr(adapter, "connect") and callable(getattr(adapter, "connect")):
        try:
            adapter.connect()
        except Exception as exc:
            if mode_key == "live":
                raise BrokerBootstrapError(
                    f"Broker '{broker_key}' connect() failed: {exc}"
                ) from exc
            print(
                f"[BROKER BOOTSTRAP WARNING] {broker_key} paper connect() failed; "
                f"continuing in paper mode: {exc}"
            )

    # Validate configuration only as a hard gate in live mode.
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
