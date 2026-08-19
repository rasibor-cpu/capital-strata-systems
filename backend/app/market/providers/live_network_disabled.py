"""Fail-closed live-network market access — unauthorized on this recovery."""

from __future__ import annotations

from typing import Any, Mapping

from backend.app.market.status import EXECUTION_ALLOWED, LIVE_NETWORK_INGESTION


class LiveNetworkMarketAccessError(RuntimeError):
    """Raised when any live/network market path is attempted."""


def _forbidden() -> None:
    raise LiveNetworkMarketAccessError(
        "live network market access is unauthorized "
        f"(live_network_ingestion={LIVE_NETWORK_INGESTION}, execution_allowed={EXECUTION_ALLOWED})"
    )


class LiveNetworkMarketProvider:
    """Any construction or fetch attempt fails closed. No sockets, no credentials."""

    provider_name = "LIVE_NETWORK_DISABLED"
    provider_version = "CONSOL.1"
    provider_status = "UNAUTHORIZED"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        _forbidden()

    def get_snapshot(self, *, symbol: str, context: Mapping[str, Any] | None = None) -> None:
        del symbol, context
        _forbidden()
