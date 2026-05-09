from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import (
    BrokerState,
    DashboardState,
)
from engine.brokers.broker_readiness import certify_broker_readiness
from engine.instruments import frontend_supported_assets


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
        selected_broker = str(
            broker_payload.get(
                "selected_broker",
                "NONE",
            )
        )
        broker_mode = str(
            broker_payload.get(
                "broker_mode",
                "paper",
            )
        )
        connected = bool(
            broker_payload.get(
                "connected",
                False,
            )
        )
        live_trading_enabled = bool(
            broker_payload.get(
                "live_trading_enabled",
                False,
            )
        )
        api_health = str(
            broker_payload.get(
                "api_health",
                "UNKNOWN",
            )
        )
        account_readiness = str(
            broker_payload.get(
                "account_readiness",
                "UNKNOWN",
            )
        )
        missing_credentials = bool(
            broker_payload.get(
                "missing_credentials",
                False,
            )
        )
        readiness = certify_broker_readiness(
            selected_broker=selected_broker,
            broker_mode=broker_mode,
            connected=connected,
            live_trading_enabled=live_trading_enabled,
            missing_credentials=missing_credentials,
            api_health=api_health,
            account_readiness=account_readiness,
        )

        broker_state = BrokerState(
            selected_broker=selected_broker,

            broker_mode=broker_mode,

            connected=connected,

            live_trading_enabled=live_trading_enabled,

            last_heartbeat=str(
                broker_payload.get(
                    "last_heartbeat",
                    "",
                )
            ),

            api_health=api_health,

            reconnect_state=str(
                broker_payload.get(
                    "reconnect_state",
                    "NONE",
                )
            ),

            supported_assets=_asset_list(
                broker_payload.get(
                    "supported_assets",
                    frontend_supported_assets(),
                )
            ),

            account_readiness=account_readiness,

            missing_credentials=missing_credentials,

            latency_ms=_safe_float(
                broker_payload.get(
                    "latency_ms",
                    0.0,
                )
            ),

            readiness_status=str(
                broker_payload.get(
                    "readiness_status",
                    readiness.status,
                )
            ),

            readiness_reasons=_string_list(
                broker_payload.get(
                    "readiness_reasons",
                    list(readiness.reasons),
                )
            ),

            account_snapshot=_mapping(
                broker_payload.get(
                    "account_snapshot",
                    broker_payload.get("broker_account_snapshot", {}),
                )
            ),

            position_snapshot=_position_snapshots(
                broker_payload.get(
                    "position_snapshot",
                    broker_payload.get("broker_position_snapshot", []),
                )
            ),
        )

        state.broker_state = broker_state

        return state


def _asset_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]

    if isinstance(value, tuple):
        return [str(item).strip().upper() for item in value if str(item).strip()]

    if isinstance(value, str):
        return [
            item.strip().upper()
            for item in value.split(",")
            if item.strip()
        ]

    return []


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]

    if isinstance(value, tuple):
        return [str(item) for item in value if str(item)]

    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]

    return []


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _position_snapshots(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
