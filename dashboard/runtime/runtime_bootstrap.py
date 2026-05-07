from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_renderer import DashboardRenderer
from dashboard.runtime.dashboard_state_factory import DashboardStateFactory


class DashboardRuntimeBootstrap:
    """
    PCNRASS-safe dashboard runtime bootstrap.

    Purpose:
    - Connect normalized runtime payloads to the dashboard state factory.
    - Render canonical DashboardState through DashboardRenderer.
    - Provide one clean runtime entrypoint for future dashboard integration.
    """

    def __init__(self) -> None:
        self.state_factory = DashboardStateFactory()
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
        state = self.state_factory.build(
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
