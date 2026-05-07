from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.dashboard_renderer import DashboardRenderer


class DashboardRuntimeBootstrap:
    """
    PCNRASS-safe dashboard runtime bootstrap.

    Purpose:
    - Connect normalized runtime payloads to the hydration coordinator.
    - Render canonical DashboardState through DashboardRenderer.
    - Provide one clean runtime entrypoint for future dashboard integration.
    """

    def __init__(self) -> None:
        self.hydration_coordinator = DashboardHydrationCoordinator()
        self.renderer = DashboardRenderer()

    def run(
        self,
        account_payload: Dict[str, Any] | None = None,
        broker_payload: Dict[str, Any] | None = None,
        positions_payload: Dict[str, Any] | None = None,
        market_payload: Dict[str, Any] | None = None,
        governance_payload: Dict[str, Any] | None = None,
        risk_payload: Dict[str, Any] | None = None,
        execution_payload: Dict[str, Any] | None = None,
        session_payload: Dict[str, Any] | None = None,
        diagnostics_payload: Dict[str, Any] | None = None,
    ) -> str:
        state = self.hydration_coordinator.hydrate(
            account_payload=account_payload,
            broker_payload=broker_payload,
            positions_payload=positions_payload,
            market_payload=market_payload,
            governance_payload=governance_payload,
            risk_payload=risk_payload,
            execution_payload=execution_payload,
            session_payload=session_payload,
            diagnostics_payload=diagnostics_payload,
        )

        return self.renderer.render(state)
