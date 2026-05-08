from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import (
    BrokerState,
    DashboardState,
)


class BrokerStateBuilder:
    """
    Build BrokerState payloads for DashboardState.

    PURPOSE
    -------
    Normalize broker/runtime connectivity information into
    structured dashboard-safe broker state.

    RULES
    -----
    - builder must not place trades
    - builder must not mutate broker balances
    - builder must not override broker authority
    """

    def build(
        self,
        *,
        broker_payload: Dict[str, Any],
        state: DashboardState,
    ) -> DashboardState:

        broker_state = BrokerState(
            selected_broker=str(
                broker_payload.get(
                    "selected_broker",
                    "NONE",
                )
            ),

            broker_mode=str(
                broker_payload.get(
                    "broker_mode",
                    "paper",
                )
            ),

            connected=bool(
                broker_payload.get(
                    "connected",
                    False,
                )
            ),

            live_trading_enabled=bool(
                broker_payload.get(
                    "live_trading_enabled",
                    False,
                )
            ),

            last_heartbeat=str(
                broker_payload.get(
                    "last_heartbeat",
                    "",
                )
            ),
        )

        state.broker_state = broker_state

        return state