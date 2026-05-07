from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.dashboard_state_factory import DashboardStateFactory


class DashboardHydrationCoordinator:
    """
    PCNRASS-safe dashboard hydration coordinator.

    Purpose:
    - Provide one explicit hydration boundary for runtime payloads.
    - Preserve existing builder/factory behavior while migration proceeds.
    - Give future live-dashboard adapters a stable target.

    Rules:
    - Do not render.
    - Do not access brokers, engines, or execution paths directly.
    - Do not mutate source payload dictionaries.
    """

    def __init__(
        self,
        state_factory: DashboardStateFactory | None = None,
    ) -> None:
        self.state_factory = state_factory or DashboardStateFactory()

    def hydrate(
        self,
        *,
        account_payload: Dict[str, Any] | None = None,
        broker_payload: Dict[str, Any] | None = None,
        positions_payload: Dict[str, Any] | None = None,
        market_payload: Dict[str, Any] | None = None,
        governance_payload: Dict[str, Any] | None = None,
        risk_payload: Dict[str, Any] | None = None,
        execution_payload: Dict[str, Any] | None = None,
        session_payload: Dict[str, Any] | None = None,
        diagnostics_payload: Dict[str, Any] | None = None,
    ) -> DashboardState:
        """
        Hydrate canonical DashboardState from normalized runtime payloads.

        This intentionally delegates to DashboardStateFactory in package 1.
        A later milestone can move factory orchestration behind this boundary
        without changing callers.
        """

        return self.state_factory.build(
            account_payload=dict(account_payload or {}),
            broker_payload=dict(broker_payload or {}),
            positions_payload=dict(positions_payload or {}),
            market_payload=dict(market_payload or {}),
            governance_payload=dict(governance_payload or {}),
            risk_payload=dict(risk_payload or {}),
            execution_payload=dict(execution_payload or {}),
            session_payload=dict(session_payload or {}),
            diagnostics_payload=dict(diagnostics_payload or {}),
        )
