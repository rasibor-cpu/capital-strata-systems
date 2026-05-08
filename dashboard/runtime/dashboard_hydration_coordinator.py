from __future__ import annotations

import logging
from typing import Any, Dict

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.dashboard_state_factory import DashboardStateFactory


LOGGER = logging.getLogger(__name__)


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

        LOGGER.debug(
            "Dashboard hydration coordinator started payloads=%s",
            _payload_summary(
                account_payload=account_payload,
                broker_payload=broker_payload,
                positions_payload=positions_payload,
                market_payload=market_payload,
                governance_payload=governance_payload,
                risk_payload=risk_payload,
                execution_payload=execution_payload,
                session_payload=session_payload,
                diagnostics_payload=diagnostics_payload,
            ),
        )

        state = self.state_factory.build(
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

        LOGGER.debug(
            "Dashboard hydration coordinator completed session_id=%s "
            "resolved_mode=%s open_positions=%s",
            state.session_id,
            state.resolved_mode(),
            state.total_open_positions,
        )

        return state


def _payload_summary(
    **payloads: Dict[str, Any] | None,
) -> dict[str, dict[str, int | bool]]:
    return {
        name: {
            "present": isinstance(payload, dict) and bool(payload),
            "field_count": len(payload) if isinstance(payload, dict) else 0,
        }
        for name, payload in payloads.items()
    }
