from __future__ import annotations

import html
import socket
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.runtime.coinbase_live_read_only_balance_promotion import (
    SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY,
    apply_coinbase_balance_only_promotion,
)
from dashboard.mission_control.app import create_app
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.runtime.frontend_contract import build_frontend_payload


REQUIRED_LABELS = (
    "Available / Free",
    "Portfolio Value",
    "Session P&L",
    "Execution Status",
    "Liquidity / Margin",
    "Current Holdings / Positions",
    "Maturity / Expiry Profile",
)


class _NetworkGuard:
    def __init__(self) -> None:
        self.external_attempts: list[object] = []
        self._original_connect = socket.socket.connect
        self._original_create_connection = socket.create_connection

    def __enter__(self) -> "_NetworkGuard":
        guard = self

        def connect(self_sock, address, *args, **kwargs):
            host = address[0] if isinstance(address, tuple) and address else address
            if str(host) not in {"127.0.0.1", "::1", "localhost"}:
                guard.external_attempts.append(address)
                raise OSError("external network blocked")
            return guard._original_connect(self_sock, address, *args, **kwargs)

        def create_connection(address, *args, **kwargs):
            host = address[0] if isinstance(address, tuple) and address else address
            if str(host) not in {"127.0.0.1", "::1", "localhost"}:
                guard.external_attempts.append(address)
                raise OSError("external network blocked")
            return guard._original_create_connection(address, *args, **kwargs)

        socket.socket.connect = connect  # type: ignore[method-assign]
        socket.create_connection = create_connection  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        socket.socket.connect = self._original_connect  # type: ignore[method-assign]
        socket.create_connection = self._original_create_connection  # type: ignore[assignment]


def test_offline_executive_overview_smoke_renders_cockpit_without_external_network() -> None:
    with _NetworkGuard() as guard:
        client = TestClient(create_app())
        response = client.get("/mission-control/executive-overview")
        text = html.unescape(response.text)

    assert response.status_code == 200
    for label in REQUIRED_LABELS:
        assert label in text
    assert "Advisory / read-only" in text
    assert "Execution allowed: false" in text or "execution allowed false" in text.lower()
    assert "Live trading blocked" in text
    assert "Broker execution unarmed" in text
    assert guard.external_attempts == []


def test_mission_control_displays_unavailable_instead_of_numeric_zero() -> None:
    frontend = build_frontend_payload(
        {
            "pnl_summary": {
                "realized_pnl": "UNAVAILABLE",
                "unrealized_pnl": "UNAVAILABLE",
                "net_pnl": "UNAVAILABLE",
                "account_equity": "UNAVAILABLE",
            },
            "position_state": {"open_count": "UNAVAILABLE"},
            "open_positions": {"total": "UNAVAILABLE"},
            "account_summary": {
                "cash_balance": None,
                "total_equity": None,
                "buying_power": None,
            },
        }
    )
    state = build_mission_control_state({"frontend_payload": frontend}, allow_mock=False)
    portfolio = state["portfolio"]
    assert portfolio["realized_pnl"] == "UNAVAILABLE"
    assert portfolio["unrealized_pnl"] == "UNAVAILABLE"
    assert portfolio["net_pnl"] == "UNAVAILABLE"
    assert portfolio["open_positions"] == "UNAVAILABLE"
    assert isinstance(frontend["sections"]["pnl_summary"]["realized_pnl"], float)
    assert frontend["sections"]["pnl_summary"]["realized_pnl"] == 0.0


def test_coinbase_balance_only_shows_balances_and_hides_unevidenced_pnl() -> None:
    raw = apply_coinbase_balance_only_promotion(
        {"account_summary": {}, "pnl_summary": {}, "position_state": {}, "open_positions": {}},
        selected_broker="COINBASE",
        canonical_mode="LIVE_READ_ONLY",
        coinbase_validation={
            "validation_status": "PASS",
            "balances_loaded": True,
            "broker_validation": {
                "validation_status": "PASS",
                "balances_loaded": True,
                "canonical_account_snapshot": {
                    "balances_loaded": True,
                    "cash": 88.0,
                    "equity": 99.0,
                    "buying_power": 77.0,
                    "available_balance": 77.0,
                    "margin_available": 77.0,
                    "timestamp": datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc).isoformat(),
                },
            },
        },
        now=datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc),
    )
    frontend = build_frontend_payload(raw)
    state = build_mission_control_state({"frontend_payload": frontend}, allow_mock=False)
    portfolio = state["portfolio"]
    assert portfolio["cash"] == 88.0
    assert portfolio["portfolio_value"] == 99.0
    assert portfolio["available_free"] == 77.0
    assert portfolio["realized_pnl"] == "UNAVAILABLE"
    assert portfolio["session_pnl"] == "UNAVAILABLE"
    assert portfolio["open_positions"] == "UNAVAILABLE"
    assert portfolio["session_pnl_by_instrument"] == "UNAVAILABLE"
    assert portfolio["maturity_expiry"]["status"] == "UNAVAILABLE"
    assert portfolio["source"] == SOURCE_COINBASE_LIVE_READ_ONLY_BALANCE_ONLY
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False
