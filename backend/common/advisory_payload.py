from __future__ import annotations

from typing import Any


class AdvisoryPayloadBuilder:
    """Build immutable-like advisory payloads to prevent live execution authorization leaks."""

    @staticmethod
    def build(status: str, **payload: Any) -> dict[str, Any]:
        response = {
            "status": status,
            "advisory_only": True,
            "execution_allowed": False,
        }
        # Safely integrate custom fields while enforcing locks
        response.update(payload)
        
        # Strictly enforce advisory boundaries (overwrite any override attempts)
        response["advisory_only"] = True
        response["execution_allowed"] = False
        
        # Enforce safety limits on trading and broker execution flags if present
        if "live_trading_blocked" in response:
            response["live_trading_blocked"] = True
        if "broker_execution_armed" in response:
            response["broker_execution_armed"] = False
            
        return response
