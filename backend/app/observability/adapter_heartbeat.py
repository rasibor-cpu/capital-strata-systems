"""
Adapter Heartbeat Helper
Centralized helper to avoid import duplication across adapters.
"""

from backend.app.observability.health import DEFAULT_REGISTRY


def beat(adapter_name: str, note: str = "ok") -> None:
    try:
        DEFAULT_REGISTRY.beat(adapter_name, note)
    except Exception:
        # Observability must never break adapters
        pass
