from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AdvisoryPayloadBuilder:
    """Build immutable-like advisory payloads to prevent live execution authorization leaks."""

    @staticmethod
    def lock(
        payload: Mapping[str, Any] | None = None,
        *,
        force_live_block: bool = False,
    ) -> dict[str, Any]:
        response = dict(payload) if isinstance(payload, Mapping) else {}

        # Advisory safety defaults are always enforced regardless of input.
        response["advisory_only"] = True
        response["execution_allowed"] = False

        # Keep optional live/broker lock fields deterministic when present.
        if force_live_block or "live_trading_blocked" in response:
            response["live_trading_blocked"] = True
        if force_live_block or "broker_execution_armed" in response:
            response["broker_execution_armed"] = False
        return response

    @staticmethod
    def build(status: str, **payload: Any) -> dict[str, Any]:
        response = AdvisoryPayloadBuilder.lock({
            "status": status,
            **payload,
        })
        return response
